import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from database import client_diagnostics as diagnostics
import server
from database import clinical_synthesis_worker as worker


class ClientDiagnosticsTests(unittest.TestCase):
    def test_details_drop_clinical_text_credentials_unknown_codes_and_invalid_types(self):
        self.assertEqual(diagnostics.safe_details({
            'revision': 4, 'stage': 'brief', 'error_code': 'brief_request_too_large',
            'prompt': 'private transcript', 'exception': 'Bearer secret', 'model': 'private',
            'input_tokens': True, 'attempt': -1, 'context_bytes': 'wrong',
        }), {'revision': 4, 'stage': 'brief', 'error_code': 'brief_request_too_large'})
        self.assertEqual(diagnostics.safe_details({'stage': {}, 'error_code': []}), {})

    def test_provider_error_body_never_becomes_a_diagnostic_message(self):
        self.assertEqual(diagnostics.failure_code(RuntimeError('OpenAI request failed (400): private payload'), 'insights'), 'provider_request_failed')
        self.assertEqual(diagnostics.failure_code(ValueError('private clinical text'), 'publication'), 'publication_failed')
        self.assertEqual(diagnostics.failure_code(RuntimeError('Brief request exceeds the testing input limit; narrow the accepted context.'), 'brief'), 'brief_request_too_large')

    def test_events_are_scoped_bounded_ordered_and_sanitized_on_read(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        now = datetime.now(timezone.utc)
        cursor.fetchall.side_effect = [
            [dict(id='stage', event_type='brief_requested', level='info',
                  created_at=now, details={'revision': 4, 'prompt': 'private'}),
             dict(id='unsafe', event_type='private clinical message', level='info',
                  created_at=now, details={})],
            [dict(id='queued', event_type='evidence_claim_accepted', desired_insights_revision=4,
                  created_at=now - timedelta(seconds=10))], [], [],
        ]
        cursor.fetchone.return_value = None
        result = diagnostics.read_timeline(conn, organization_id='org', client_id='client')
        self.assertEqual([e['id'] for e in result['events']], ['stage', 'refresh-queued'])
        self.assertEqual(result['events'][0]['details'], {'revision': 4})
        self.assertNotIn('private', str(result))
        for call in cursor.execute.call_args_list:
            self.assertEqual(call.args[1], ('org', 'client'))
            self.assertIn('organization_id=%s AND client_id=%s', call.args[0])
        self.assertLessEqual(len(result['events']), 200)

    def test_append_never_saves_exception_bodies_and_retains_only_30_days(self):
        conn = MagicMock()
        diagnostics.append_event(conn, organization_id='org', client_id='client',
            event_type='synthesis_failed', level='error', details={'stage':'brief','prompt':'private'})
        cursor = conn.cursor.return_value.__enter__.return_value
        self.assertEqual(cursor.execute.call_args_list[0].args[1][-1].obj, {'stage': 'brief'})
        self.assertIn("INTERVAL '30 days'", cursor.execute.call_args_list[1].args[0])

    def test_endpoint_requires_existing_client_access_but_no_developer_role(self):
        context = {'organization_id': 'org', 'client_id': 'client'}
        with patch.object(server, 'connect'), patch.object(server, 'resolve_therapist_client_context', return_value=context) as resolve, patch.object(server.client_diagnostics, 'read_timeline', return_value={'events': []}) as read:
            self.assertEqual(server.get_client_diagnostics('client', 'Bearer user'), {'events': []})
            self.assertEqual(resolve.call_args.args[1:], ('Bearer user', 'client'))
            self.assertEqual(read.call_args.kwargs, context)
        with patch.object(server, 'connect'), patch.object(server, 'resolve_therapist_client_context', side_effect=HTTPException(status_code=403)), patch.object(server.client_diagnostics, 'read_timeline') as read:
            with self.assertRaises(HTTPException):
                server.get_client_diagnostics('another-client', 'Bearer user')
            read.assert_not_called()

    def test_worker_records_failure_stage_without_exception_message(self):
        job = dict(organization_id='org', client_id='client', processing_insights_revision=4, attempt_count=2)
        with patch.dict('os.environ', {'OPENAI_API_KEY':'test','INSIGHTS_MODEL':'test','PRE_SESSION_MODEL':'test'}), \
                patch.object(worker, 'connect'), \
                patch.object(worker.synthesis_refresh, 'claim_due_insights_refresh', return_value=job), \
                patch.object(worker, 'build_clinical_context', side_effect=ValueError('Clinical context exceeds the bounded input limit.')), \
                patch.object(worker.client_diagnostics, 'append_event') as append, \
                patch.object(worker.synthesis_refresh, 'fail_insights_refresh') as fail:
            self.assertTrue(worker.process_one())
        self.assertEqual(append.call_args.kwargs['event_type'], 'synthesis_failed')
        self.assertEqual(append.call_args.kwargs['details'],
                         {'stage':'context','error_code':'context_too_large','revision':4,'attempt':2})
        self.assertEqual(fail.call_args.kwargs['error_code'], 'context_too_large')

    def test_diagnostic_write_failure_does_not_abort_the_worker(self):
        job = dict(organization_id='org', client_id='client', processing_insights_revision=4, attempt_count=1)
        with patch.dict('os.environ', {'OPENAI_API_KEY':'test','INSIGHTS_MODEL':'test','PRE_SESSION_MODEL':'test'}), \
                patch.object(worker, 'connect'), \
                patch.object(worker.synthesis_refresh, 'claim_due_insights_refresh', return_value=job), \
                patch.object(worker, 'build_clinical_context', side_effect=ValueError('Clinical context exceeds the bounded input limit.')), \
                patch.object(worker.client_diagnostics, 'append_event', side_effect=RuntimeError('private diagnostic error')), \
                patch.object(worker.synthesis_refresh, 'fail_insights_refresh') as fail, \
                self.assertLogs(worker.LOGGER, level='WARNING') as logs:
            self.assertTrue(worker.process_one())
        self.assertTrue(fail.called)
        self.assertNotIn('private diagnostic error', str(logs.output))


if __name__ == '__main__':
    unittest.main()
