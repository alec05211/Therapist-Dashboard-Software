"""Client-scoped operational events. Never persist prompts or exception messages."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Json

EVENTS = {
    'synthesis_claimed': 'Worker started an Insights refresh',
    'context_loaded': 'Eligible clinical context loaded',
    'insights_requested': 'Insights model request started',
    'insights_repair_requested': 'Insights validation repair requested',
    'insights_validated': 'Insights passed validation',
    'brief_requested': 'Pre-session brief request started',
    'brief_validated': 'Pre-session brief passed validation',
    'synthesis_published': 'Insights refresh published',
    'synthesis_failed': 'Insights refresh failed',
}
ERRORS = {
    'context_too_large': 'Clinical context exceeds its input limit',
    'insights_request_too_large': 'Insights request exceeds its input limit',
    'brief_request_too_large': 'Pre-session brief request exceeds its input limit',
    'insights_validation_failed': 'Insights did not pass evidence validation',
    'brief_validation_failed': 'Pre-session brief did not pass evidence validation',
    'provider_timeout': 'Model provider request timed out',
    'provider_unreachable': 'Model provider could not be reached',
    'provider_rate_limited': 'Model provider rate limit reached',
    'provider_request_failed': 'Model provider rejected the request',
    'provider_output_incomplete': 'Model provider returned incomplete output',
    'publication_failed': 'Validated synthesis could not be published',
    'no_accepted_source_evidence': 'No eligible source evidence is available',
    'synthesis_provider_not_configured': 'Synthesis provider is not configured',
    'unexpected_error': 'An unexpected processing error occurred',
    'synthesis_generation_failed': 'Generation failed; detailed diagnostics were not recorded',
}
STAGES = {'claim', 'context', 'insights', 'brief', 'publication'}
NUMBER_FIELDS = {'revision', 'attempt', 'source_count', 'context_bytes', 'request_bytes',
                 'input_tokens', 'output_tokens', 'repair_attempt', 'violation_count'}


def safe_details(details: dict[str, Any] | None) -> dict[str, Any]:
    result = {}
    if not isinstance(details, dict):
        return result
    for key, value in (details or {}).items():
        if key in NUMBER_FIELDS and type(value) is int and 0 <= value <= 100_000_000:
            result[key] = value
        elif key == 'stage' and isinstance(value, str) and value in STAGES:
            result[key] = value
        elif key == 'error_code' and isinstance(value, str) and value in ERRORS:
            result[key] = value
    return result


def failure_code(exc: Exception, stage: str) -> str:
    """Inspect known internal prefixes; never return provider bodies or clinical prose."""
    message = str(exc)
    if message in {'no_accepted_source_evidence', 'synthesis_provider_not_configured'}:
        return message
    if message.startswith('Clinical context exceeds'):
        return 'context_too_large'
    if message.startswith(('Insight request exceeds', 'Insight repair request exceeds')):
        return 'insights_request_too_large'
    if message.startswith('Brief request exceeds'):
        return 'brief_request_too_large'
    if message.startswith('OpenAI output did not satisfy the longitudinal'):
        return 'insights_validation_failed'
    if message.startswith('OpenAI output did not satisfy the evidence contract'):
        return 'brief_validation_failed'
    if isinstance(exc, TimeoutError) or 'generation timed out' in message:
        return 'provider_timeout'
    if message.startswith('Could not reach OpenAI'):
        return 'provider_unreachable'
    if message.startswith('OpenAI request failed (429)'):
        return 'provider_rate_limited'
    if message.startswith('OpenAI request failed'):
        return 'provider_request_failed'
    if message.startswith(('OpenAI returned no structured', 'OpenAI insight generation was incomplete',
                           'OpenAI returned invalid structured')):
        return 'provider_output_incomplete'
    return 'publication_failed' if stage == 'publication' else 'unexpected_error'


def append_event(connection, *, organization_id, client_id, event_type, details=None, level='info'):
    if event_type not in EVENTS or level not in {'info', 'warning', 'error'}:
        raise ValueError('Unsupported diagnostic event')
    with connection.cursor() as cursor:
        cursor.execute('''INSERT INTO app.client_diagnostic_events
            (organization_id,client_id,event_type,level,details) VALUES (%s,%s,%s,%s,%s)''',
            (organization_id, client_id, event_type, level, Json(safe_details(details))))
        cursor.execute('''DELETE FROM app.client_diagnostic_events
            WHERE organization_id=%s AND client_id=%s
              AND created_at < CURRENT_TIMESTAMP - INTERVAL '30 days' ''', (organization_id, client_id))


def read_timeline(connection, *, organization_id, client_id):
    """Project bounded, allowlisted metadata from durable records and worker events."""
    events = []
    scope = (organization_id, client_id)

    def add(event_id, at, message, level='info', details=None):
        if at:
            events.append(dict(id=str(event_id), timestamp=at.isoformat(), message=message,
                               level=level, details=safe_details(details)))

    with connection.cursor() as cursor:
        cursor.execute('''SELECT id,event_type,level,details,created_at FROM app.client_diagnostic_events
            WHERE organization_id=%s AND client_id=%s
              AND created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
            ORDER BY created_at DESC,id DESC LIMIT 200''', scope)
        for row in cursor.fetchall():
            if row['event_type'] not in EVENTS:
                continue
            details = safe_details(row['details'])
            message = EVENTS[row['event_type']]
            if details.get('error_code'):
                message += ': ' + ERRORS[details['error_code']]
            add(row['id'], row['created_at'], message, row['level'], details)
        cursor.execute('''SELECT id,event_type,desired_insights_revision,created_at
            FROM app.clinical_synthesis_refresh_events WHERE organization_id=%s AND client_id=%s
            ORDER BY created_at DESC,id DESC LIMIT 200''', scope)
        # Event names are constrained by the synthesis queue, but still allowlist on read.
        from database.synthesis_refresh import EVENT_TYPES
        for row in cursor.fetchall():
            if row['event_type'] in EVENT_TYPES:
                add('refresh-' + str(row['id']), row['created_at'],
                    row['event_type'].replace('_', ' ').capitalize() + ' → Insights refresh queued',
                    details={'revision': row['desired_insights_revision']})
        cursor.execute('''SELECT runtime_id,status,created_at,updated_at FROM app.session_storage_jobs
            WHERE organization_id=%s AND client_id=%s ORDER BY created_at DESC LIMIT 50''', scope)
        for row in cursor.fetchall():
            add('upload-' + row['runtime_id'], row['created_at'], 'Session upload registered')
            messages = {'UPLOADING': 'Session upload in progress', 'IN_PROGRESS': 'Transcription processing',
                        'COMPLETED': 'Transcript and draft clinical note saved', 'FAILED': 'Session processing failed'}
            if row['status'] in messages:
                add('processing-' + row['runtime_id'], row['updated_at'], messages[row['status']],
                    'error' if row['status'] == 'FAILED' else 'info')
        cursor.execute('''SELECT session_id,status,created_at,updated_at,attempt_count
            FROM app.journey_proposal_analysis_jobs WHERE organization_id=%s AND client_id=%s
            ORDER BY created_at DESC LIMIT 50''', scope)
        for row in cursor.fetchall():
            add('proposals-queued-' + str(row['session_id']), row['created_at'], 'Transcript evidence analysis queued')
            messages = {'pending': 'Transcript evidence analysis pending', 'running': 'Transcript evidence analysis running',
                        'completed': 'Transcript evidence proposals saved', 'failed': 'Transcript evidence analysis failed',
                        'blocked': 'Transcript evidence analysis is not configured'}
            if row['status'] in messages:
                add('proposals-state-' + str(row['session_id']), row['updated_at'], messages[row['status']],
                    'error' if row['status'] == 'failed' else 'info', {'attempt': row['attempt_count']})
        cursor.execute('''SELECT status,desired_insights_revision,published_insights_revision,
            processing_insights_revision,pending_event_count,attempt_count,last_error_code,last_attempt_at,updated_at
            FROM app.clinical_synthesis_refresh_state WHERE organization_id=%s AND client_id=%s''', scope)
        state = cursor.fetchone()
    summary = dict(status='idle', desired_revision=0, published_revision=0, queued_event_count=0, attempt_count=0, error=None)
    if state:
        summary = dict(status=state['status'], desired_revision=state['desired_insights_revision'],
                       published_revision=state['published_insights_revision'],
                       queued_event_count=max(0, int(state['pending_event_count'])) if state['desired_insights_revision'] > state['published_insights_revision'] else 0,
                       attempt_count=state['attempt_count'],
                       error=ERRORS.get(state['last_error_code'], 'Generation failed') if state['last_error_code'] else None)
        # Legacy attempts have only a last-attempt watermark, not a historical stage trace.
        if state['last_attempt_at']:
            add('last-attempt', state['last_attempt_at'], 'Latest worker attempt started',
                details={'revision': state['processing_insights_revision']})
        if state['status'] == 'failed':
            add('current-failure', state['updated_at'], summary['error'] or 'Insights refresh failed', 'error')
    events.sort(key=lambda row: (row['timestamp'], row['id']), reverse=True)
    return {'events': list(reversed(events[:200])), 'summary': summary,
            'checked_at': datetime.now(timezone.utc).isoformat(), 'retention_days': 30}
