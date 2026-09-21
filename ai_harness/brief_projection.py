"""Deterministic, source-preserving brief projection from accepted insight history."""

from typing import Any


def project_accepted_insights(packet: dict[str, Any] | None, journey_entries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Present clinician-approved items without inventing new clinical claims."""
    sections = {title: [] for title in ('Important trajectory', 'Open loops', 'Relevant history')}
    titles = {
        'trajectory': 'Important trajectory',
        'theme': 'Important trajectory',
        'open_thread': 'Open loops',
    }
    journey_titles = {
        'theme': 'Important trajectory', 'breakthrough': 'Important trajectory',
        'resolution': 'Important trajectory', 'open_thread': 'Open loops',
    }
    selected = 0
    for entry in journey_entries or []:
        if selected >= 8:
            break
        if entry['status'] != 'accepted' or not entry['evidence']:
            continue
        sections[journey_titles.get(entry['category'], 'Relevant history')].append({
            'text': entry['text'], 'sources': entry['evidence'],
        })
        selected += 1
    for item in packet['items'] if packet else []:
        if selected >= 8:
            break
        content = item['content']
        text = next((content[key].strip() for key in ('text', 'summary', 'narrative', 'title')
                     if isinstance(content.get(key), str) and content[key].strip()), None)
        if not text:
            continue
        sources = []
        for evidence in item['evidence']:
            session_id = evidence.get('session_id')
            if not session_id:
                continue
            source_id = evidence.get('transcript_segment_id') or evidence.get('clinical_note_version_id')
            if not source_id:
                continue
            source = {
                'evidence_id': source_id,
                'session_id': f'session-{session_id}',
                'session_label': evidence.get('session_label') or 'Completed session',
            }
            if 'segment_index' in evidence:
                source.update(segment_index=evidence['segment_index'], start=evidence['start'],
                              end=evidence['end'], quote=evidence['quote'])
            sources.append(source)
        if not sources:
            continue
        sections[titles.get(item['kind'], 'Relevant history')].append({'text': text, 'sources': sources})
        selected += 1
    version = f"insights v{packet['snapshot_version']}" if packet else 'approved journey history'
    return {
        'status': f"REVIEW DRAFT · {version}",
        'review_note': 'Drawn only from therapist-accepted insights and journey entries. Review cited session material before relying on this brief.',
        'source_insight_snapshot_id': packet['snapshot_id'] if packet else None,
        'sections': [{'title': title, 'items': items} for title, items in sections.items() if items],
    }
