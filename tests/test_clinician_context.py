import unittest
from unittest.mock import patch

from fastapi import HTTPException

import server

from ai_harness.clinician_context import with_clinician_guidance


def entry(state='accepted', **overrides):
    return {
        'id': 'entry-1', 'session_id': 'session-1', 'status': state,
        'category': 'important_quote', 'text': 'Explore what changed.',
        'evidence': [{'evidence_id': 'segment-1', 'session_id': 'session-1', 'quote': 'I asked for help.'}],
        **overrides,
    }


class ClinicianContextTests(unittest.TestCase):
    def test_excludes_unreviewed_and_retracted_guidance(self):
        for state in ('proposed', 'rejected', 'hidden', 'stale', 'disputed'):
            self.assertIsNone(with_clinician_guidance(None, [entry(state)]))

    def test_keeps_interpretation_separate_from_original_words(self):
        packet = {'items': [{'kind': 'theme'}], 'snapshot_id': 'snapshot-1'}
        result = with_clinician_guidance(packet, [entry()])
        self.assertEqual(result['items'], packet['items'])
        self.assertNotIn('clinician_guidance', packet)
        guidance = result['clinician_guidance'][0]
        self.assertEqual(guidance['clinician_interpretation'], 'Explore what changed.')
        self.assertEqual(guidance['evidence'][0]['quote'], 'I asked for help.')

    def test_rejects_missing_or_mismatched_source(self):
        for evidence in ([], [{'evidence_id': 'segment-2', 'session_id': 'session-2', 'quote': 'Other session.'}]):
            self.assertIsNone(with_clinician_guidance(None, [entry(evidence=evidence)]))

    def test_bounds_selection_and_supports_guidance_without_snapshot(self):
        result = with_clinician_guidance(None, [entry(id=str(i)) for i in range(20)])
        self.assertEqual(len(result['clinician_guidance']), 8)
        self.assertEqual(result['items'], [])

    def test_route_scopes_guidance_and_allows_no_snapshot(self):
        with patch.object(server, 'connect'), patch.object(server, 'authorize_clinical_access') as authorize, patch.object(server.LongitudinalRecordRepository, 'build_pre_session_context_packet', return_value=None), patch.object(server.client_journey, 'list_entries', return_value=[entry()]) as listing:
            result = server.get_pre_session_context_packet('client', 'org', 'Bearer therapist')
        self.assertEqual(authorize.call_args.kwargs['client_id'], 'client')
        self.assertEqual(listing.call_args.args[1:], ('org', 'client'))
        self.assertEqual(listing.call_args.kwargs['status'], 'accepted')
        self.assertEqual(len(result['clinician_guidance']), 1)

    def test_route_does_not_read_guidance_when_access_denied(self):
        with patch.object(server, 'connect'), patch.object(server, 'authorize_clinical_access', side_effect=HTTPException(403)), patch.object(server.client_journey, 'list_entries') as listing:
            with self.assertRaises(HTTPException):
                server.get_pre_session_context_packet('client', 'org', 'Bearer other')
        listing.assert_not_called()
