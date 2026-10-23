"""Durable post-upload evidence discovery for completed session transcripts."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import timedelta
from uuid import uuid4

from psycopg import Error as PsycopgError
from psycopg.types.json import Json

from ai_harness.journey_proposals import ANALYZER_VERSION, discover_openai_evidence_claims
from database.connection import connect
from database.clinical_context import build_clinical_context


logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3


def enqueue(cursor, storage, transcript_version_id):
    """Request exactly one analysis for a session transcript version."""
    cursor.execute("""INSERT INTO app.journey_proposal_analysis_jobs
        (session_id, organization_id, client_id, source_transcript_version_id, status, not_before)
        VALUES (%s,%s,%s,%s,'pending',CURRENT_TIMESTAMP)
        ON CONFLICT (session_id) DO UPDATE SET
          source_transcript_version_id=EXCLUDED.source_transcript_version_id,
          status=CASE
            WHEN app.journey_proposal_analysis_jobs.source_transcript_version_id=EXCLUDED.source_transcript_version_id
             AND app.journey_proposal_analysis_jobs.status='completed' THEN 'completed'
            ELSE 'pending'
          END,
          not_before=CASE
            WHEN app.journey_proposal_analysis_jobs.source_transcript_version_id=EXCLUDED.source_transcript_version_id
             AND app.journey_proposal_analysis_jobs.status='completed'
              THEN app.journey_proposal_analysis_jobs.not_before
            ELSE CURRENT_TIMESTAMP
          END,
          updated_at=CURRENT_TIMESTAMP""",
        (storage['session_id'], storage['organization_id'], storage['client_id'], transcript_version_id))


def _policy(cursor, job):
    """Enable proposal analysis for every client when the provider is configured."""
    api_key = os.getenv('OPENAI_API_KEY')
    model = os.getenv('JOURNEY_PROPOSAL_MODEL') or os.getenv('PRE_SESSION_MODEL')
    if not api_key or not model:
        return None, None, 'model_configuration_missing'
    return api_key, model, None


def _claim_job(session_id=None, organization_id=None, client_id=None):
    token = uuid4().hex
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""UPDATE app.journey_proposal_analysis_jobs
            SET status='pending', worker_token=NULL, lease_expires_at=NULL,
                last_error_code='expired_worker_lease', updated_at=CURRENT_TIMESTAMP
            WHERE status='running' AND lease_expires_at < CURRENT_TIMESTAMP""")
        parameters = []
        scope = "status IN ('pending','blocked') AND not_before <= CURRENT_TIMESTAMP"
        if session_id:
            scope += ' AND session_id=%s'
            parameters.append(session_id)
        if organization_id:
            scope += ' AND organization_id=%s'
            parameters.append(organization_id)
        if client_id:
            scope += ' AND client_id=%s'
            parameters.append(client_id)
        cursor.execute(f"""SELECT * FROM app.journey_proposal_analysis_jobs
            WHERE {scope}
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED LIMIT 1""", parameters)
        job = cursor.fetchone()
        if not job:
            return None
        api_key, model, blocked_reason = _policy(cursor, job)
        if blocked_reason:
            cursor.execute("""UPDATE app.journey_proposal_analysis_jobs
                SET status='blocked', last_error_code=%s, updated_at=CURRENT_TIMESTAMP
                WHERE session_id=%s""", (blocked_reason, job['session_id']))
            return None
        cursor.execute("""UPDATE app.journey_proposal_analysis_jobs
            SET status='running', worker_token=%s,
                lease_expires_at=CURRENT_TIMESTAMP + INTERVAL '10 minutes',
                attempt_count=attempt_count + 1, updated_at=CURRENT_TIMESTAMP
            WHERE session_id=%s""", (token, job['session_id']))
        return {**job, 'worker_token': token, 'api_key': api_key, 'model': model,
                'attempt_count': job['attempt_count'] + 1}


def _input_bundle(job):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        cursor.execute("""SELECT sequence_number, starts_at_seconds, ends_at_seconds,
                speaker_label, content
            FROM app.transcript_segments
            WHERE transcript_version_id=%s ORDER BY sequence_number""",
            (job['source_transcript_version_id'],))
        segments = [{
            'segment_key': str(row['sequence_number']),
            'start': float(row['starts_at_seconds']),
            'end': float(row['ends_at_seconds']),
            'speaker': row['speaker_label'],
            'text': row['content'],
        } for row in cursor.fetchall()]
        packet = build_clinical_context(connection,
            organization_id=job['organization_id'], client_id=job['client_id'],
            exclude_session_id=job['session_id'])
    if not segments:
        raise ValueError('The transcript has no analyzable segments.')
    fingerprint = hashlib.sha256(json.dumps({
        'analyzer_version': ANALYZER_VERSION,
        'segments': segments,
        'clinical_context': packet,
    }, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
    return segments, packet, fingerprint


def _publish(job, claims, metadata, packet, fingerprint):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT sequence_number, id FROM app.transcript_segments
            WHERE transcript_version_id=%s""", (job['source_transcript_version_id'],))
        segment_ids = {str(row['sequence_number']): row['id'] for row in cursor.fetchall()}
        cursor.execute("""SELECT DISTINCT segment.sequence_number
            FROM app.client_journey_entries entry
            JOIN app.client_journey_evidence evidence ON evidence.journey_entry_id=entry.id
            JOIN app.transcript_segments segment ON segment.id=evidence.transcript_segment_id
            WHERE entry.session_id=%s AND entry.status <> 'proposed'""", (job['session_id'],))
        reviewed_segments = {str(row['sequence_number']) for row in cursor.fetchall()}
        if claims:
            cursor.execute("""DELETE FROM app.client_journey_entries
                WHERE session_id=%s
                  AND source_provider IN ('amazon_healthscribe', 'openai_transcript_analysis')
                  AND status='proposed'""", (job['session_id'],))
        for claim in claims:
            evidence_keys = sorted(set(claim['evidence_segment_keys']), key=int)
            if reviewed_segments.intersection(evidence_keys):
                continue
            source_key = 'openai:' + hashlib.sha256(json.dumps({
                'evidence': evidence_keys, 'focus': claim['synthesis_focus'],
            }, sort_keys=True).encode('utf-8')).hexdigest()[:32]
            categories = claim['categories']
            analysis = {
                'analysis_status': 'generated',
                'claim_summary': claim['claim_summary'],
                'relationship': claim['relationship'],
                'related_insight_item_ids': claim['related_insight_item_ids'],
            }
            cursor.execute("""INSERT INTO app.client_journey_entries
                (organization_id, client_id, session_id, source_summary_key, source_provider,
                 category, categories, content, source_insight_snapshot_id,
                 proposal_generator_name, proposal_generator_version, proposal_analysis)
                VALUES (%s,%s,%s,%s,'openai_transcript_analysis',%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (session_id, source_summary_key) DO NOTHING RETURNING id""",
                (job['organization_id'], job['client_id'], job['session_id'], source_key,
                 categories[0], categories, claim['synthesis_focus'],
                 (packet or {}).get('snapshot_id'), 'OpenAI transcript evidence analyzer',
                 f"{ANALYZER_VERSION}:{metadata['model']}", Json(analysis)))
            entry = cursor.fetchone()
            if entry:
                for key in evidence_keys:
                    cursor.execute("""INSERT INTO app.client_journey_evidence
                        (journey_entry_id, transcript_segment_id) VALUES (%s,%s)""",
                        (entry['id'], segment_ids[key]))
        cursor.execute("""UPDATE app.journey_proposal_analysis_jobs
            SET status='completed', input_fingerprint=%s,
                generator_name='OpenAI transcript evidence analyzer', generator_version=%s,
                source_insight_snapshot_id=%s, response_id=%s, usage=%s,
                last_error_code=NULL, worker_token=NULL, lease_expires_at=NULL,
                completed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
            WHERE session_id=%s AND worker_token=%s""",
            (fingerprint, f"{ANALYZER_VERSION}:{metadata['model']}",
             (packet or {}).get('snapshot_id'), metadata.get('response_id'),
             Json(metadata.get('usage') or {}), job['session_id'], job['worker_token']))
        if cursor.rowcount != 1:
            raise RuntimeError('Proposal analysis lease was lost before publication.')


def _fail(job, error_code):
    retry = job['attempt_count'] < MAX_ATTEMPTS
    delay_minutes = 2 ** max(job['attempt_count'] - 1, 0)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""UPDATE app.journey_proposal_analysis_jobs
            SET status=%s, not_before=CURRENT_TIMESTAMP + %s,
                last_error_code=%s, worker_token=NULL, lease_expires_at=NULL,
                updated_at=CURRENT_TIMESTAMP
            WHERE session_id=%s AND worker_token=%s""",
            ('pending' if retry else 'failed', timedelta(minutes=delay_minutes), error_code,
             job['session_id'], job['worker_token']))


def process_one(*, session_id=None, organization_id=None, client_id=None):
    """Run one due job. Failures remain durable and never fail session ingestion."""
    try:
        job = _claim_job(session_id, organization_id, client_id)
    except (RuntimeError, ValueError, PsycopgError) as exc:
        logger.warning('Transcript evidence analysis could not claim a job: %s', type(exc).__name__)
        return False
    if not job:
        return False
    try:
        segments, packet, fingerprint = _input_bundle(job)
        claims, metadata = discover_openai_evidence_claims(
            segments=segments, insights_context=packet,
            api_key=job['api_key'], model=job['model'])
        _publish(job, claims, metadata, packet, fingerprint)
    except (RuntimeError, ValueError, PsycopgError) as exc:
        logger.warning('Transcript evidence analysis will retry or remain failed: %s', type(exc).__name__)
        _fail(job, type(exc).__name__)
    return True


def process_due_for_client(organization_id, client_id, limit=3):
    for _ in range(limit):
        if not process_one(organization_id=organization_id, client_id=client_id):
            break
