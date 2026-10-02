import asyncio
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException, UploadFile
import server


class AudioUploadTests(unittest.TestCase):
    def test_active_job_discovery_resumes_server_monitor(self):
        storage = {'audio_key': 'clients/client/sessions/id/audio/recording.wav'}
        active = [{'id': 'session-id', 'job_name': 'job-id', 'storage': storage,
                   'status': 'IN_PROGRESS', 'detail': None,
                   'created_at': '2026-10-02T12:00:00+00:00',
                   'updated_at': '2026-10-02T12:01:00+00:00'}]
        tasks = BackgroundTasks()
        request = SimpleNamespace(state=SimpleNamespace(care_context={'client_id': 'client'}))
        with patch.object(server.organization_storage, 'active_jobs', return_value=active):
            result = server.transcription_jobs(tasks, request)
        self.assertEqual(result[0]['id'], 'session-id')
        self.assertIsNone(result[0]['appointment_id'])
        self.assertNotIn('storage', result[0])
        self.assertEqual(len(tasks.tasks), 1)
        self.assertIs(tasks.tasks[0].func, server.process_job)

    def test_uploading_job_is_visible_but_not_resumed_before_handoff(self):
        active = [{'id': 'session-id', 'job_name': 'job-id', 'storage': {},
                   'status': 'UPLOADING', 'detail': None,
                   'created_at': '2026-10-02T12:00:00+00:00',
                   'updated_at': '2026-10-02T12:00:30+00:00'}]
        tasks = BackgroundTasks()
        request = SimpleNamespace(state=SimpleNamespace(care_context={'client_id': 'client'}))
        with patch.object(server.organization_storage, 'active_jobs', return_value=active):
            result = server.transcription_jobs(tasks, request)
        self.assertEqual(result[0]['status'], 'UPLOADING')
        self.assertEqual(tasks.tasks, [])

    def test_completed_upload_keeps_playback_format(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server, 'RECORDINGS_DIRECTORY', Path(directory)), patch.object(server, 'configuration', return_value=('input', 'output', 'role')), patch.object(server.boto3, 'client') as aws, patch.object(server, 'segments_from_healthscribe', return_value=[]), patch.object(server, 'summary_from_healthscribe', return_value=[]):
            session = Path(directory) / 'session-test'
            session.mkdir()
            (session / 'recording.mp3').write_bytes(b'audio fixture')
            aws.return_value.get_medical_scribe_job.return_value = {'MedicalScribeJob': {'MedicalScribeJobStatus': 'COMPLETED', 'MedicalScribeOutput': {'TranscriptFileUri': 's3://output/transcript.json', 'ClinicalDocumentUri': 's3://output/note.json'}}}
            aws.return_value.get_object.side_effect = [{'Body': io.BytesIO(b'{}')}, {'Body': io.BytesIO(b'{}')}]
            server.process_job('session-test', 'job-test', 'recording.mp3')
            transcript = json.loads((session / 'transcript.json').read_text())
            self.assertEqual(transcript['audio']['mime_type'], 'audio/mpeg')
            self.assertEqual(json.loads(server.status_path('session-test').read_text())['status'], 'COMPLETED')

    def test_completed_upload_reports_application_owned_processing_stages(self):
        storage = {'bucket': 'output', 'region': 'us-east-1'}
        with tempfile.TemporaryDirectory() as directory, patch.object(server, 'RECORDINGS_DIRECTORY', Path(directory)), patch.object(server.boto3, 'client') as aws, patch.object(server, 'segments_from_healthscribe', return_value=[]), patch.object(server, 'summary_from_healthscribe', return_value=[]), patch.object(server.organization_storage, 'set_job_status') as set_status, patch.object(server.organization_storage, 'publish_results'):
            session = Path(directory) / 'session-test'
            session.mkdir()
            (session / 'recording.wav').write_bytes(b'audio fixture')
            aws.return_value.get_medical_scribe_job.return_value = {'MedicalScribeJob': {'MedicalScribeJobStatus': 'COMPLETED', 'MedicalScribeOutput': {'TranscriptFileUri': 's3://output/transcript.json', 'ClinicalDocumentUri': 's3://output/note.json'}}}
            aws.return_value.get_object.side_effect = [{'Body': io.BytesIO(b'{}')}, {'Body': io.BytesIO(b'{}')}]

            server.process_job('session-test', 'job-test', 'recording.wav', storage)

            self.assertEqual(
                [call.args[1] for call in set_status.call_args_list],
                ['RETRIEVING_RESULTS', 'PREPARING_TRANSCRIPT', 'SAVING_SESSION', 'COMPLETED'],
            )

    def test_invalid_empty_and_oversize_files_do_not_reach_aws(self):
        for name, content, limit, expected in [('audio.txt', b'hello', 100, 415), ('audio.wav', b'', 100, 400), ('audio.mp3', b'12345', 4, 413)]:
            with self.subTest(name=name), patch.object(server, 'MAX_AUDIO_UPLOAD_BYTES', limit), patch.object(server.boto3, 'client') as aws:
                with self.assertRaises(HTTPException) as error:
                    asyncio.run(server.transcribe(BackgroundTasks(), UploadFile(filename=name, file=io.BytesIO(content))))
                self.assertEqual(error.exception.status_code, expected)
                aws.assert_not_called()

    def test_uploaded_formats_are_preserved_and_job_is_queued(self):
        for extension in ('.WAV', '.mp3', '.m4a', '.webm'):
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as directory, patch.object(server, 'RECORDINGS_DIRECTORY', Path(directory)), patch.object(server, 'configuration', return_value=('input', 'output', 'role')), patch.object(server.boto3, 'client') as aws:
                tasks = BackgroundTasks()
                result = asyncio.run(server.transcribe(tasks, UploadFile(filename='external'+extension, file=io.BytesIO(b'audio fixture'))))
                recording = Path(directory) / result['id'] / ('recording'+extension.lower())
                self.assertEqual(recording.read_bytes(), b'audio fixture')
                self.assertEqual(server.session_recording(result['id'], recording.name).media_type, server.AUDIO_MIME_TYPES[extension.lower()])
                args = aws.return_value.start_medical_scribe_job.call_args.kwargs
                self.assertTrue(args['Media']['MediaFileUri'].endswith(extension.lower()))
                self.assertEqual(args['Settings']['MaxSpeakerLabels'], server.HEALTHSCRIBE_MAX_SPEAKERS)
                self.assertEqual(result['status'], 'IN_PROGRESS')
                self.assertEqual(len(tasks.tasks), 1)
                self.assertIs(tasks.tasks[0].func, server.process_job)

    def test_aws_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server, 'RECORDINGS_DIRECTORY', Path(directory)), patch.object(server, 'configuration', return_value=('input', 'output', 'role')), patch.object(server.boto3, 'client') as aws:
            aws.return_value.upload_file.side_effect = OSError('Upload failed')
            with self.assertRaises(HTTPException) as error:
                asyncio.run(server.transcribe(BackgroundTasks(), UploadFile(filename='audio.wav', file=io.BytesIO(b'audio fixture'))))
            self.assertEqual(error.exception.status_code, 500)
            aws.return_value.start_medical_scribe_job.assert_not_called()
