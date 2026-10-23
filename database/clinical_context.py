"""One client-scoped context assembly boundary for discovery and synthesis."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from ai_harness.clinical_context import CONTEXT_POLICY_VERSION
from database import client_journey
from database.longitudinal_records import LongitudinalRecordRepository


def fingerprint(packet: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(packet, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def build_clinical_context(connection, *, organization_id, client_id, exclude_session_id=None):
    """Take a consistent read of saved records; never include unsaved UI state.

    Callers own the read transaction. Excluding the session under discovery keeps
    its baseline proposals from biasing independent discovery of that transcript.
    """
    entries = client_journey.list_entries(connection, organization_id, client_id)
    entries = [entry for entry in entries
               if entry['session_id'].removeprefix('session-') != str(exclude_session_id)]
    snapshot = LongitudinalRecordRepository(connection).get_latest_insight_snapshot(
        organization_id=organization_id, client_id=client_id)
    sources = {}
    decisions, pending, constraints = [], [], []
    for entry in entries:
        decision = {key: entry[key] for key in ('id', 'session_id', 'text', 'status', 'categories')}
        if entry['status'] == 'accepted':
            decisions.append(decision)
            for source in entry['evidence']:
                selected = sources.setdefault(source['evidence_id'], {
                    **source, 'source_type': 'transcript_segment',
                    'transcript_segment_id': source['evidence_id'],
                    'accepted_guidance': [], 'categories': [],
                })
                if entry['text'] not in selected['accepted_guidance']:
                    selected['accepted_guidance'].append(entry['text'])
                selected['categories'] = sorted(set(selected['categories'] + entry['categories']))
        elif entry['status'] == 'proposed':
            pending.append({**decision, 'evidence': entry['evidence']})
        else:
            constraints.append(decision)
    with connection.cursor() as cursor:
        cursor.execute("""SELECT * FROM (
            SELECT DISTINCT ON (note.session_id) note.id, note.session_id,
                note.version_number, note.content, note.finalized_at,
                COALESCE(job.storage->>'label', 'Completed session') AS session_label
            FROM app.clinical_note_versions note
            LEFT JOIN app.session_storage_jobs job ON job.session_id=note.session_id
            WHERE note.organization_id=%s AND note.client_id=%s AND note.status='finalized'
            ORDER BY note.session_id, note.version_number DESC
        ) latest ORDER BY finalized_at DESC, id LIMIT 31""", (organization_id, client_id))
        notes = cursor.fetchall()
    for note in notes[:30]:
        source_id = str(note['id'])
        sources[source_id] = {
            'evidence_id': source_id, 'source_type': 'finalized_clinical_note',
            'clinical_note_version_id': source_id, 'version_number': note['version_number'],
            'session_id': f"session-{note['session_id']}", 'session_label': note['session_label'],
            'finalized_at': note['finalized_at'].isoformat(), 'content': note['content'],
            'accepted_guidance': [], 'categories': [],
        }
    interpretations = []
    for item in (snapshot or {}).get('items', []):
        if item['review_state'] in {'hidden', 'stale', 'disputed'}:
            constraints.append({'id': item['id'], 'status': item['review_state'], 'origin': 'insight'})
        elif item['kind'] in {'therapist_curated', 'client_context'}:
            curated = {**item, 'origin': 'clinician_curated', 'status': item['review_state']}
            if item['review_state'] == 'accepted':
                decisions.append(curated)
            else:
                pending.append(curated)
        else:
            interpretations.append(item)
    ordered_sources = list(sources.values())
    packet = {
        'policy_version': CONTEXT_POLICY_VERSION,
        'snapshot_id': (snapshot or {}).get('id'),
        'snapshot_version': (snapshot or {}).get('version'),
        # A snapshot-wide summary may still mention an item hidden since publication.
        # In that case use only the individually state-filtered interpretations.
        'snapshot_summary': ((snapshot or {}).get('content') if not any(
            item['review_state'] in {'hidden', 'stale', 'disputed'}
            for item in (snapshot or {}).get('items', [])) else None),
        'snapshot_created_at': (snapshot or {}).get('created_at'),
        'source_evidence': ordered_sources[:120],
        'clinician_decisions': decisions[:120],
        'pending_proposals': pending[:40],
        'review_constraints': constraints,
        'generated_interpretations': interpretations[:30],
        'coverage': {
            'source_count': len(ordered_sources), 'sources_omitted': max(0, len(ordered_sources)-120),
            'pending_omitted': max(0, len(pending)-40),
            'decisions_omitted': max(0, len(decisions)-120),
            'interpretations_omitted': max(0, len(interpretations)-30),
            'older_notes_omitted': len(notes) > 30,
            'snapshot_available': snapshot is not None,
        },
    }
    # Prefer finalized notes without letting transcript volume crowd them out.
    packet['source_evidence'] = ([s for s in ordered_sources if s['source_type'] == 'finalized_clinical_note']
                                 + [s for s in ordered_sources if s['source_type'] == 'transcript_segment'])[:120]
    if len(json.dumps(packet, ensure_ascii=False).encode('utf-8')) > 110_000:
        raise ValueError('Clinical context exceeds the bounded input limit.')
    return packet
