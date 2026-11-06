from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import server
from database import organization_storage as storage


class SessionDurationTests(unittest.TestCase):
    def test_saved_duration_does_not_download_audio(self):
        with patch.object(storage, 'restore_artifact') as restore:
            self.assertEqual(storage.get_recording_duration({'recording_duration_seconds': 73.5}), 73.5)
        restore.assert_not_called()

    def test_legacy_duration_uses_catalogued_audio_and_saves_only_metadata(self):
        scope = dict(runtime_id='session-id', session_id='id', organization_id='org', client_id='client', audio_key='private/audio.wav')
        with patch.object(storage, 'restore_artifact', return_value=Path('audio.wav')) as restore, patch.object(storage, 'recording_duration', return_value=71.25), patch.object(storage, 'connect') as connect:
            self.assertEqual(storage.get_recording_duration(scope), 71.25)
        self.assertEqual(restore.call_args.args[:2], (scope, 'audio.wav'))
        cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        self.assertEqual(cursor.execute.call_args.args[1], (71.25, 'session-id', 'id', 'org', 'client'))

    def test_therapist_duration_requires_authorized_completed_job(self):
        for job in (None, {'status': 'IN_PROGRESS'}):
            request = SimpleNamespace(state=SimpleNamespace(storage_job=job))
            with self.subTest(job=job), patch.object(storage, 'get_recording_duration') as duration:
                with self.assertRaises(HTTPException) as error:
                    server.session_recording_duration('session-id', request)
                self.assertEqual(error.exception.status_code, 404)
                duration.assert_not_called()

    def test_client_duration_cannot_read_another_relationship_session(self):
        context = {'organization_id': 'org', 'client_id': 'client'}
        with patch.object(server, 'connect'), patch.object(server, 'resolve_sharing_context', return_value=context), patch.object(storage, 'find_job', return_value=None) as find, patch.object(storage, 'get_recording_duration') as duration:
            with self.assertRaises(HTTPException) as error:
                server.shared_session_recording_duration('other-session', 'Bearer client')
        self.assertEqual(error.exception.status_code, 404)
        find.assert_called_once_with(context, 'other-session')
        duration.assert_not_called()


if __name__ == '__main__':
    unittest.main()
