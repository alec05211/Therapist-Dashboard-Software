"""Organization-owned storage and durable session/artifact catalog.

Callers must authorize a client context before calling these functions. Bucket
names and keys are resolved here, never accepted from a browser request.
"""
import hashlib
from pathlib import Path
from uuid import UUID, uuid4

import boto3
from psycopg.types.json import Json

from database.connection import connect
from database import session_review


def session_prefix(client_id, session_id):
    return f"clients/{UUID(str(client_id))}/sessions/{UUID(str(session_id))}/"


def create_upload(context, suffix, actor_subject):
    session_id = str(uuid4())
    runtime_id = f"session-{session_id}"
    job_name = f"healthscribe-{uuid4().hex}"
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT storage.* FROM app.organization_storage storage
            JOIN app.organizations organization ON organization.id=storage.organization_id
            JOIN app.clients client ON client.organization_id=organization.id
            WHERE organization.id=%s AND client.id=%s
              AND organization.status='active' AND client.status='active'""",
            (context['organization_id'], context['client_id']))
        binding = cursor.fetchone()
        if not binding:
            raise RuntimeError("Private storage has not been provisioned for this organization.")
        cursor.execute("SELECT to_regclass('app.transcript_speaker_labels') AS relation")
        if not cursor.fetchone()['relation']:
            raise RuntimeError('Session review database migration has not been applied.')
        cursor.execute("SELECT to_regclass('app.client_journey_entries') AS relation")
        if not cursor.fetchone()['relation']:
            raise RuntimeError('Client journey database migration has not been applied.')
        prefix = session_prefix(context['client_id'], session_id)
        storage = {key: str(binding[key]) for key in ('bucket', 'region', 'kms_key_arn', 'healthscribe_role_arn')}
        storage.update(organization_id=context['organization_id'], client_id=context['client_id'],
                       session_id=session_id, prefix=prefix, audio_key=f'{prefix}audio/recording{suffix}',
                       runtime_id=runtime_id, job_name=job_name)
        cursor.execute("""INSERT INTO app.sessions (id, organization_id, client_id, status, started_at, created_by_user_id)
            VALUES (%s, %s, %s, 'processing', CURRENT_TIMESTAMP,
                (SELECT id FROM app.application_users WHERE auth0_subject=%s AND status='active'))""",
            (session_id, context['organization_id'], context['client_id'], actor_subject))
        cursor.execute("""INSERT INTO app.session_storage_jobs
            (runtime_id, session_id, organization_id, client_id, job_name, storage, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'UPLOADING')""",
            (runtime_id, session_id, context['organization_id'], context['client_id'], job_name, Json(storage)))
    return storage


def set_job_status(storage, status, detail=None):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""UPDATE app.session_storage_jobs SET status=%s, detail=%s, updated_at=CURRENT_TIMESTAMP
            WHERE runtime_id=%s AND organization_id=%s AND client_id=%s""",
            (status, detail, storage['runtime_id'], storage['organization_id'], storage['client_id']))
        if status == 'COMPLETED':
            cursor.execute("UPDATE app.sessions SET status='review' WHERE id=%s AND organization_id=%s AND client_id=%s",
                           (storage['session_id'], storage['organization_id'], storage['client_id']))


def find_job(context, runtime_id):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT runtime_id, storage, status, detail FROM app.session_storage_jobs
            WHERE runtime_id=%s AND organization_id=%s AND client_id=%s""",
            (runtime_id, context['organization_id'], context['client_id']))
        return cursor.fetchone()


def completed_jobs(context):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT job.runtime_id AS id,
                COALESCE(job.storage->>'label', 'Uploaded session') AS label,
                COALESCE(session.started_at, job.created_at) AS created_at
            FROM app.session_storage_jobs job
            JOIN app.sessions session ON session.id=job.session_id
            WHERE job.organization_id=%s AND job.client_id=%s AND job.status='COMPLETED'
            ORDER BY COALESCE(session.started_at, job.created_at) DESC""",
            (context['organization_id'], context['client_id']))
        return [{**row, 'created_at': row['created_at'].isoformat(), 'text': ''} for row in cursor.fetchall()]


def completed_job_records(context):
    """Return authorized completed jobs for server-side material projection."""
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT job.runtime_id, job.storage,
                COALESCE(job.storage->>'label', 'Uploaded session') AS label,
                COALESCE(session.started_at, job.created_at) AS created_at
            FROM app.session_storage_jobs job
            JOIN app.sessions session ON session.id=job.session_id
            WHERE job.organization_id=%s AND job.client_id=%s AND job.status='COMPLETED'
            ORDER BY COALESCE(session.started_at, job.created_at) DESC""",
            (context['organization_id'], context['client_id']))
        return cursor.fetchall()


def put_artifact(storage, path, artifact_type, key, content_type, source='application'):
    if not key.startswith(storage['prefix']):
        raise ValueError('Artifact must remain within its client/session prefix.')
    body = Path(path).read_bytes()
    s3 = boto3.client('s3', region_name=storage['region'])
    result = s3.put_object(Bucket=storage['bucket'], Key=key, Body=body, ContentType=content_type,
                           ServerSideEncryption='aws:kms', SSEKMSKeyId=storage['kms_key_arn'])
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""INSERT INTO app.clinical_artifacts
            (organization_id, client_id, session_id, artifact_type, source, storage_bucket, object_key,
             object_version_id, content_type, byte_size, sha256_checksum, encryption_key_reference)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (storage['organization_id'], storage['client_id'], storage['session_id'], artifact_type, source,
             storage['bucket'], key, result.get('VersionId'), content_type, len(body), hashlib.sha256(body).hexdigest(), storage['kms_key_arn']))
        return str(cursor.fetchone()['id'])


def publish_results(storage, directory, segments, clinical_note, raw_transcript=None, raw_note=None):
    directory = Path(directory)
    artifact_ids = {}
    for name, kind in [('healthscribe-transcript.json', 'raw_transcript'), ('clinical-note.json', 'raw_clinical_document'), ('transcript.json', 'normalized_transcript_export')]:
        artifact_ids[kind] = put_artifact(storage, directory / name, kind, f"{storage['prefix']}transcripts/{name}", 'application/json', 'healthscribe')
    session_review.persist_result(storage, segments, clinical_note, artifact_ids['raw_transcript'], raw_transcript, raw_note)


def restore_artifact(storage, filename, directory):
    """Restore only a catalogued artifact, pinned to its recorded S3 version."""
    if filename == Path(storage['audio_key']).name:
        key = storage['audio_key']
    elif filename == 'transcript.json':
        key = f"{storage['prefix']}transcripts/transcript.json"
    else:
        raise FileNotFoundError('Artifact not available.')
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT object_version_id FROM app.clinical_artifacts
            WHERE organization_id=%s AND client_id=%s AND session_id=%s AND storage_bucket=%s
              AND object_key=%s AND lifecycle_state='active' AND deleted_at IS NULL
            ORDER BY created_at DESC LIMIT 1""",
            (storage['organization_id'], storage['client_id'], storage['session_id'], storage['bucket'], key))
        artifact = cursor.fetchone()
    if not artifact:
        raise FileNotFoundError('Artifact not available.')
    arguments = {'Bucket': storage['bucket'], 'Key': key}
    if artifact['object_version_id']:
        arguments['VersionId'] = artifact['object_version_id']
    result = boto3.client('s3', region_name=storage['region']).get_object(**arguments)
    path = Path(directory) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(result['Body'].read())
    return path
