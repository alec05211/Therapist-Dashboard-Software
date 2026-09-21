"""Live non-clinical roundtrip. DB changes roll back; only its test S3 version is removed."""
from contextlib import contextmanager
import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
import wave

import boto3
from dotenv import load_dotenv
from psycopg import Rollback

from database.connection import connect
from database import organization_storage as storage

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
cleanup = None
try:
    with connect() as connection:
        @contextmanager
        def existing_connection():
            yield connection

        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("""SELECT client.organization_id, client.id AS client_id, actor.auth0_subject
                    FROM app.clients client
                    JOIN app.client_portal_accounts portal ON portal.client_id=client.id
                    JOIN app.client_therapist_access access ON access.client_id=client.id AND access.organization_id=client.organization_id
                    JOIN app.organization_practitioners practitioner ON practitioner.id=access.practitioner_id
                    JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id
                    JOIN app.application_users actor ON actor.id=membership.user_id
                    WHERE portal.synthetic_case_key='heartwell-sadic' AND access.revoked_at IS NULL""")
                rows = cursor.fetchall()
                assert len(rows) == 1
                row = rows[0]
            context = {key: str(row[key]) for key in ('organization_id', 'client_id')}
            with patch.object(storage, 'connect', existing_connection), tempfile.TemporaryDirectory() as directory:
                target = storage.create_upload(context, '.wav', row['auth0_subject'])
                source = Path(directory) / 'verification.wav'
                with wave.open(str(source), 'wb') as audio:
                    audio.setnchannels(1)
                    audio.setsampwidth(2)
                    audio.setframerate(16000)
                    audio.writeframes(b'\0\0' * 160)
                artifact_id = storage.put_artifact(target, source, 'audio_recording', target['audio_key'], 'audio/wav')
                with connection.cursor() as cursor:
                    cursor.execute('SELECT object_version_id FROM app.clinical_artifacts WHERE id=%s', (artifact_id,))
                    version = cursor.fetchone()['object_version_id']
                assert version
                cleanup = (target, version)
                s3 = boto3.client('s3', region_name=target['region'])
                head = s3.head_object(Bucket=target['bucket'], Key=target['audio_key'], VersionId=version)
                assert head['ServerSideEncryption'] == 'aws:kms'
                assert head['SSEKMSKeyId'] == target['kms_key_arn']
                restored = storage.restore_artifact(target, 'recording.wav', Path(directory) / 'cache')
                assert restored.read_bytes() == source.read_bytes()
                assert storage.find_job({**context, 'client_id': str(uuid4())}, target['runtime_id']) is None
                assert storage.find_job({**context, 'organization_id': str(uuid4())}, target['runtime_id']) is None
                storage.set_job_status(target, 'COMPLETED')
                assert any(job['id'] == target['runtime_id'] for job in storage.completed_jobs(context))
            raise Rollback()
    print('Live storage verified: organization/session association, KMS encryption, versioned S3 roundtrip, cross-client isolation; database changes rolled back.')
finally:
    if cleanup:
        target, version = cleanup
        boto3.client('s3', region_name=target['region']).delete_object(Bucket=target['bucket'], Key=target['audio_key'], VersionId=version)
        print('Removed the exact temporary verification object version. No HealthScribe job submitted.')
