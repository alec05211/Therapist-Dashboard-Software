import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import server
from database import session_review


class SessionReviewTests(unittest.TestCase):
    def setUp(self):
        self.storage = {key: str(uuid4()) for key in ('organization_id', 'client_id', 'session_id')}
        self.storage.update(runtime_id=f"session-{self.storage['session_id']}", audio_key='clients/c/sessions/s/audio/recording.wav')

    def test_invalid_passages_never_open_a_database_transaction(self):
        with patch.object(session_review, 'connect') as connect:
            for segments in ([], [{'start': 'NaN', 'end': 1, 'text': 'x'}],
                             [{'start': 2, 'end': 1, 'text': 'x'}],
                             [{'start': 0, 'end': 1, 'text': ''}]):
                with self.assertRaises(ValueError):
                    session_review.persist_result(self.storage, segments, [], str(uuid4()))
            connect.assert_not_called()

    def test_ingestion_commits_passages_draft_and_completion_in_one_connection(self):
        connection = MagicMock()
        cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        version_id = uuid4()
        cursor.fetchone.side_effect = [{'id': uuid4()}, None, {'id': version_id}]
        cursor.rowcount = 1
        with patch.object(session_review, 'connect', return_value=connection):
            session_review.persist_result(self.storage,
                                          [{'start': 0.1234, 'end': 1.2, 'speaker': 'PATIENT', 'text': 'Hello.'}],
                                          [{'name': 'History', 'items': ['Draft.']}], str(uuid4()))
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any('INSERT INTO app.transcript_segments' in sql for sql in statements))
        self.assertTrue(any('INSERT INTO app.synthesis_versions' in sql for sql in statements))
        self.assertLess(next(i for i, sql in enumerate(statements) if 'INSERT INTO app.synthesis_versions' in sql),
                        next(i for i, sql in enumerate(statements) if "status='COMPLETED'" in sql))
        segment_call = next(call for call in cursor.execute.call_args_list if 'INSERT INTO app.transcript_segments' in call.args[0])
        self.assertEqual(segment_call.args[1][2:4], (Decimal('0.123'), Decimal('1.200')))

    def test_review_endpoint_returns_database_result_without_s3_restore(self):
        result = {'segments': [{'start': 0, 'end': 1, 'text': 'Hello.'}], 'clinical_note': [], 'speakers': {}}
        request = SimpleNamespace(state=SimpleNamespace(storage_job={'storage': self.storage}))
        with patch.object(session_review, 'read_result', return_value=result), patch.object(server.organization_storage, 'restore_artifact') as restore:
            self.assertIs(server.transcript(self.storage['runtime_id'], request), result)
            restore.assert_not_called()

    def test_read_result_uses_ordered_passages_and_provider_draft(self):
        connection = MagicMock()
        cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            {'id': uuid4(), 'created_at': datetime(2026, 9, 20, tzinfo=timezone.utc)},
            {'content': {'clinical_note': [{'name': 'History', 'items': ['Draft.']}]}}
        ]
        cursor.fetchall.side_effect = [
            [{'starts_at_seconds': Decimal('0.100'), 'ends_at_seconds': Decimal('1.200'), 'speaker_label': 'PATIENT', 'content': 'Hello.'}],
            [{'source_label': 'PATIENT', 'display_label': 'Client'}]
        ]
        with patch.object(session_review, 'connect', return_value=connection):
            result = session_review.read_result(self.storage)
        self.assertEqual(result['segments'], [{'start': 0.1, 'end': 1.2, 'speaker': 'PATIENT', 'text': 'Hello.'}])
        self.assertEqual(result['speakers'], {'PATIENT': 'Client'})
        self.assertEqual(result['clinical_note'][0]['items'], ['Draft.'])
        self.assertEqual(result['recording_url'], f"/recordings/{self.storage['runtime_id']}/recording.wav")
