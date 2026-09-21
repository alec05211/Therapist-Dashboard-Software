import asyncio
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import BackgroundTasks, UploadFile
from starlette.requests import Request

import server
from database import organization_storage as storage


class OrganizationStorageTests(unittest.TestCase):
    def setUp(self):
        self.client_id, self.session_id, self.organization_id = [str(uuid4()) for _ in range(3)]
        prefix = storage.session_prefix(self.client_id, self.session_id)
        self.binding = dict(bucket='private-org', region='us-east-1', kms_key_arn='key', healthscribe_role_arn='role',
                            client_id=self.client_id, session_id=self.session_id, organization_id=self.organization_id,
                            runtime_id=f'session-{self.session_id}', job_name='job', prefix=prefix,
                            audio_key=f'{prefix}audio/recording.wav')

    def test_prefix_uses_ids_and_rejects_paths(self):
        self.assertEqual(storage.session_prefix(self.client_id, self.session_id), f'clients/{self.client_id}/sessions/{self.session_id}/')
        with self.assertRaises(ValueError):
            storage.session_prefix('../another-client', self.session_id)

    def test_unprovisioned_organization_fails_before_creating_session(self):
        with patch.object(storage, 'connect') as connect:
            cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = None
            with self.assertRaises(RuntimeError):
                storage.create_upload({'organization_id': self.organization_id, 'client_id': self.client_id}, '.wav', 'therapist')
            self.assertEqual(cursor.execute.call_count, 1)

    def test_missing_review_migration_fails_before_creating_session(self):
        with patch.object(storage, 'connect') as connect:
            cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.side_effect = [{'bucket': 'private-org'}, {'relation': None}]
            with self.assertRaisesRegex(RuntimeError, 'migration'):
                storage.create_upload({'organization_id': self.organization_id, 'client_id': self.client_id}, '.wav', 'therapist')
            self.assertFalse(any('INSERT INTO app.sessions' in call.args[0] for call in cursor.execute.call_args_list))

    def test_results_complete_only_after_all_artifacts_are_catalogued(self):
        with patch.object(storage, 'put_artifact', side_effect=['raw-id', 'note-id', 'export-id']) as put, patch.object(storage.session_review, 'persist_result') as persist:
            storage.publish_results(self.binding, 'cache', [{'start': 0, 'end': 1, 'text': 'hello'}], [{'name': 'Note', 'items': ['draft']}])
            self.assertEqual(put.call_count, 3)
            self.assertTrue(all(call.args[3].startswith(self.binding['prefix']) for call in put.call_args_list))
            persist.assert_called_once_with(self.binding, [{'start': 0, 'end': 1, 'text': 'hello'}], [{'name': 'Note', 'items': ['draft']}], 'raw-id', None, None)
        with patch.object(storage, 'put_artifact', side_effect=RuntimeError('Storage unavailable')), patch.object(storage.session_review, 'persist_result') as persist:
            with self.assertRaises(RuntimeError):
                storage.publish_results(self.binding, 'cache', [], [])
            persist.assert_not_called()

    def test_uncatalogued_artifact_does_not_read_s3(self):
        with patch.object(storage, 'connect') as connect, patch.object(storage.boto3, 'client') as aws:
            connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value = None
            with self.assertRaises(FileNotFoundError):
                storage.restore_artifact(self.binding, 'transcript.json', '.')
            aws.assert_not_called()

    def test_artifact_cannot_escape_session_prefix(self):
        with patch.object(storage.boto3, 'client') as aws:
            with self.assertRaises(ValueError):
                storage.put_artifact(self.binding, 'unused', 'audio_recording', 'clients/another-client/audio.wav', 'audio/wav')
            aws.assert_not_called()

    def test_restores_exact_catalogued_version(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'connect') as connect, patch.object(storage.boto3, 'client') as aws:
            connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value = {'object_version_id': 'version-2'}
            aws.return_value.get_object.return_value = {'Body': io.BytesIO(b'{}')}
            result = storage.restore_artifact(self.binding, 'transcript.json', directory)
            self.assertEqual(result.read_bytes(), b'{}')
            aws.return_value.get_object.assert_called_once_with(Bucket='private-org', Key=f"{self.binding['prefix']}transcripts/transcript.json", VersionId='version-2')

    def test_wrong_client_session_is_denied_before_file_access(self):
        for runtime_id in (self.binding['runtime_id'], self.binding['runtime_id'].upper()):
            request = Request({'type': 'http', 'method': 'GET', 'path': f'/transcripts/{runtime_id}', 'headers': []})
            downstream = AsyncMock()
            with patch.object(server, 'connect'), patch.object(server, 'resolve_sharing_context', return_value={'organization_id': 'other', 'client_id': 'other'}), patch.object(storage, 'find_job', return_value=None):
                result = asyncio.run(server.protect_legacy_clinical_routes(request, downstream))
            self.assertEqual(result.status_code, 404)
            downstream.assert_not_called()

    def test_upload_uses_registered_bucket_and_encryption(self):
        request = SimpleNamespace(headers={}, state=SimpleNamespace(care_context={'organization_id': self.organization_id, 'client_id': self.client_id}))
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, ORGANIZATION_STORAGE_ENABLED='true'), patch.object(server, 'RECORDINGS_DIRECTORY', Path(directory)), patch.object(server, 'validate_access_token', return_value={'sub': 'therapist'}), patch.object(storage, 'create_upload', return_value=self.binding) as create, patch.object(storage, 'put_artifact') as put, patch.object(storage, 'set_job_status'), patch.object(server.boto3, 'client') as aws:
            tasks = BackgroundTasks()
            result = asyncio.run(server.transcribe(tasks, UploadFile(filename='import.wav', file=io.BytesIO(b'audio')), request))
            create.assert_called_once_with(request.state.care_context, '.wav', 'therapist')
            self.assertEqual(result['id'], self.binding['runtime_id'])
            self.assertEqual(put.call_args.args[3], self.binding['audio_key'])
            args = aws.return_value.start_medical_scribe_job.call_args.kwargs
            self.assertEqual(args['OutputBucketName'], 'private-org')
            self.assertEqual(args['OutputEncryptionKMSKeyId'], 'key')
            self.assertEqual(args['DataAccessRoleArn'], 'role')
            self.assertEqual(tasks.tasks[0].args[-1], self.binding)
