"""Database-backed review state for organization-stored HealthScribe sessions."""

from decimal import Decimal, InvalidOperation
from pathlib import Path

from psycopg.types.json import Json

from database.connection import connect
from database import client_journey


def _timing(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('HealthScribe returned an invalid segment time.') from exc
    if not number.is_finite() or number < 0:
        raise ValueError('HealthScribe returned an invalid segment time.')
    return number.quantize(Decimal('0.001'))


def persist_result(storage, segments, clinical_note, source_artifact_id, raw_transcript=None, raw_note=None):
    """Commit passages, provider draft and completed state together; retries are safe."""
    prepared = []
    for index, segment in enumerate(segments):
        start, end = _timing(segment['start']), _timing(segment['end'])
        content = segment['text']
        if end < start or not isinstance(content, str) or not content.strip():
            raise ValueError('HealthScribe returned an invalid transcript segment.')
        prepared.append((index, start, end, segment.get('speaker'), content))
    if not prepared:
        raise ValueError('HealthScribe returned no transcript passages.')
    if not isinstance(clinical_note, list):
        raise ValueError('HealthScribe returned an invalid clinical draft.')

    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT id FROM app.sessions
            WHERE id=%s AND organization_id=%s AND client_id=%s FOR UPDATE""",
            (storage['session_id'], storage['organization_id'], storage['client_id']))
        if not cursor.fetchone():
            raise ValueError('Session does not belong to this client.')
        cursor.execute("""SELECT id FROM app.transcript_versions
            WHERE session_id=%s AND organization_id=%s AND client_id=%s AND source_provider='amazon_healthscribe'
            ORDER BY version_number DESC LIMIT 1""",
            (storage['session_id'], storage['organization_id'], storage['client_id']))
        existing = cursor.fetchone()
        if not existing:
            cursor.execute("""INSERT INTO app.transcript_versions
                (organization_id, client_id, session_id, source_artifact_id, version_number, status, source_provider)
                VALUES (%s,%s,%s,%s,1,'draft','amazon_healthscribe') RETURNING id""",
                (storage['organization_id'], storage['client_id'], storage['session_id'], source_artifact_id))
            version_id = cursor.fetchone()['id']
            for index, start, end, speaker, content in prepared:
                cursor.execute("""INSERT INTO app.transcript_segments
                    (transcript_version_id, sequence_number, starts_at_seconds, ends_at_seconds, speaker_label, content)
                    VALUES (%s,%s,%s,%s,%s,%s)""",
                    (version_id, index, start, end, speaker, content))
            cursor.execute("""INSERT INTO app.synthesis_versions
                (organization_id, client_id, session_id, source_transcript_version_id,
                 version_number, status, generator_name, content)
                VALUES (%s,%s,%s,%s,1,'draft','Amazon HealthScribe',%s)""",
                (storage['organization_id'], storage['client_id'], storage['session_id'], version_id,
                 Json({'clinical_note': clinical_note})))
            if raw_transcript is not None and raw_note is not None:
                client_journey.propose_from_healthscribe(cursor, storage, raw_transcript, raw_note, version_id)
        cursor.execute("""UPDATE app.session_storage_jobs
            SET status='COMPLETED', detail=NULL, updated_at=CURRENT_TIMESTAMP
            WHERE runtime_id=%s AND session_id=%s AND organization_id=%s AND client_id=%s""",
            (storage['runtime_id'], storage['session_id'], storage['organization_id'], storage['client_id']))
        if cursor.rowcount != 1:
            raise ValueError('Session storage job was not found.')
        cursor.execute("""UPDATE app.sessions SET status='review'
            WHERE id=%s AND organization_id=%s AND client_id=%s""",
            (storage['session_id'], storage['organization_id'], storage['client_id']))


def _review_version(cursor, storage):
    cursor.execute("""SELECT transcript.id,
            COALESCE(session.started_at, transcript.created_at) AS created_at
        FROM app.transcript_versions transcript
        JOIN app.sessions session ON session.id=transcript.session_id
        WHERE transcript.session_id=%s AND transcript.organization_id=%s AND transcript.client_id=%s
        ORDER BY transcript.version_number DESC LIMIT 1""",
        (storage['session_id'], storage['organization_id'], storage['client_id']))
    return cursor.fetchone()


def read_result(storage):
    with connect() as connection, connection.cursor() as cursor:
        version = _review_version(cursor, storage)
        if not version:
            return None
        cursor.execute("""SELECT starts_at_seconds, ends_at_seconds, speaker_label, content
            FROM app.transcript_segments WHERE transcript_version_id=%s ORDER BY sequence_number""",
            (version['id'],))
        segments = [dict(start=float(row['starts_at_seconds']), end=float(row['ends_at_seconds']),
                         text=row['content'], **({'speaker': row['speaker_label']} if row['speaker_label'] else {}))
                    for row in cursor.fetchall()]
        cursor.execute("""SELECT source_label, display_label FROM app.transcript_speaker_labels
            WHERE transcript_version_id=%s""", (version['id'],))
        speakers = {row['source_label']: row['display_label'] for row in cursor.fetchall()}
        cursor.execute("""SELECT content FROM app.synthesis_versions
            WHERE session_id=%s AND organization_id=%s AND client_id=%s
            ORDER BY version_number DESC LIMIT 1""",
            (storage['session_id'], storage['organization_id'], storage['client_id']))
        draft = cursor.fetchone()
    recording_name = Path(storage['audio_key']).name
    return dict(id=storage['runtime_id'], created_at=version['created_at'].isoformat(),
                audio={'file': recording_name}, speakers=speakers,
                text=' '.join(segment['text'] for segment in segments), segments=segments,
                clinical_note=draft['content'].get('clinical_note', []) if draft else [],
                recording_url=f"/recordings/{storage['runtime_id']}/{recording_name}")


def save_speaker_labels(storage, labels, actor_subject):
    cleaned = {key.strip(): value.strip() for key, value in labels.items()
               if isinstance(key, str) and isinstance(value, str) and key.strip() and value.strip()}
    with connect() as connection, connection.cursor() as cursor:
        version = _review_version(cursor, storage)
        if not version:
            return None
        cursor.execute("""SELECT DISTINCT speaker_label FROM app.transcript_segments
            WHERE transcript_version_id=%s AND speaker_label IS NOT NULL""", (version['id'],))
        known = {row['speaker_label'] for row in cursor.fetchall()}
        if set(cleaned) - known:
            raise ValueError('Unknown transcript speaker label.')
        cursor.execute("DELETE FROM app.transcript_speaker_labels WHERE transcript_version_id=%s", (version['id'],))
        for source, display in cleaned.items():
            cursor.execute("""INSERT INTO app.transcript_speaker_labels
                (transcript_version_id, source_label, display_label, updated_by_user_id)
                VALUES (%s,%s,%s,(SELECT id FROM app.application_users WHERE auth0_subject=%s AND status='active'))""",
                (version['id'], source, display, actor_subject))
    return cleaned
