import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

import server
from ai_harness.brief_projection import project_accepted_insights


class BriefProjectionTests(unittest.TestCase):
    def test_only_source_linked_accepted_packet_items_become_brief_text(self):
        session_id = str(uuid4())
        segment_id = str(uuid4())
        packet = {
            'snapshot_id': str(uuid4()), 'snapshot_version': 3,
            'items': [
                {'kind': 'trajectory', 'content': {'text': 'Client described asking for priorities earlier.'},
                 'evidence': [{'session_id': session_id, 'transcript_segment_id': segment_id,
                               'segment_index': 4, 'start': 12.5, 'end': 16.0, 'quote': 'I asked before I felt overwhelmed.'}]},
                {'kind': 'open_thread', 'content': {'text': 'Unsupported statement.'}, 'evidence': []},
            ],
        }
        brief = project_accepted_insights(packet)
        self.assertEqual(brief['source_insight_snapshot_id'], packet['snapshot_id'])
        self.assertEqual(len(brief['sections']), 1)
        item = brief['sections'][0]['items'][0]
        self.assertEqual(item['text'], 'Client described asking for priorities earlier.')
        self.assertEqual(item['sources'][0]['session_id'], f'session-{session_id}')
        self.assertEqual(item['sources'][0]['segment_index'], 4)
        self.assertNotIn('Unsupported statement.', str(brief))

    def test_brief_route_uses_scoped_accepted_context_endpoint(self):
        packet = {'snapshot_id': str(uuid4()), 'snapshot_version': 1, 'items': []}
        with patch.object(server, 'connect'), patch.object(server, 'authorize_clinical_access') as authorize, patch.object(server.LongitudinalRecordRepository, 'build_pre_session_context_packet', return_value=packet), patch.object(server.client_journey, 'list_entries', return_value=[]):
            brief = server.get_current_pre_session_brief('client', 'org', 'Bearer therapist')
        self.assertEqual(authorize.call_args.kwargs['client_id'], 'client')
        self.assertEqual(brief['sections'], [])

    def test_brief_route_preserves_no_accepted_history_response(self):
        with patch.object(server, 'connect'), patch.object(server, 'authorize_clinical_access'), patch.object(server.LongitudinalRecordRepository, 'build_pre_session_context_packet', return_value=None), patch.object(server.client_journey, 'list_entries', return_value=[]):
            with self.assertRaises(HTTPException) as error:
                server.get_current_pre_session_brief('client', 'org', 'Bearer therapist')
        self.assertEqual(error.exception.status_code, 404)

    def test_synthetic_fixture_routes_are_not_registered(self):
        paths = {route.path for route in server.app.routes}
        self.assertFalse(any(path.startswith('/demo/heartwell-sadic') for path in paths))
