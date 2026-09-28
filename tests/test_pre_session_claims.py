import copy
import unittest
from ai_harness.pre_session import validate_pre_session_response, resolve_brief, assemble_brief_parts
from ai_harness.brief_service import brief_input

class ClaimTests(unittest.TestCase):
    def setUp(self):
        self.evidence = [{'evidence_id': 'a', 'session_id': 'one', 'quote': 'Work kept me late.'}, {'evidence_id': 'b', 'session_id': 'two', 'quote': 'I stayed late again.'}]
        self.response = {'sections': [{'title': 'Important trajectory', 'items': [{'text': 'Overwork recurred across sessions.', 'evidence_ids': ['a', 'b'], 'claims': [{'phrase': 'Overwork', 'occurrence': 0, 'scope': 'single_exchange', 'evidence_ids': ['a']}, {'phrase': 'recurred', 'occurrence': 0, 'scope': 'cross_session', 'evidence_ids': ['a', 'b']}]}]}]}
    def test_paraphrased_claims_resolve_to_their_own_sources(self):
        item = resolve_brief(self.response, self.evidence)['sections'][0]['items'][0]
        self.assertEqual([s['evidence_id'] for s in item['claims'][0]['sources']], ['a'])
        self.assertEqual(len(item['claims'][1]['sources']), 2)
    def test_missing_phrase_unknown_ids_and_overlap_rejected(self):
        for field, value in [('phrase', 'unwritten'), ('evidence_ids', ['invented']), ('occurrence', 3)]:
            changed = copy.deepcopy(self.response)
            changed['sections'][0]['items'][0]['claims'][0][field] = value
            self.assertTrue(validate_pre_session_response(changed, self.evidence))
        self.response['sections'][0]['items'][0]['claims'][1]['phrase'] = 'Overwork'
        self.assertTrue(validate_pre_session_response(self.response, self.evidence))
    def test_recurrence_requires_distinct_sessions(self):
        self.evidence[1]['session_id'] = 'one'
        self.assertTrue(validate_pre_session_response(self.response, self.evidence))
    def test_missing_claims_rejected(self):
        del self.response['sections'][0]['items'][0]['claims']
        self.assertTrue(validate_pre_session_response(self.response, self.evidence))
    def test_context_fingerprint_changes_with_correction(self):
        brief = resolve_brief(self.response, self.evidence)
        before = brief_input(brief)[0]
        brief['sections'][0]['items'][0]['sources'][0]['quote'] = 'Corrected source'
        self.assertNotEqual(before, brief_input(brief)[0])

    def test_parts_build_exact_repeated_phrase_locations(self):
        response = {'sections': [{'title': 'Active focus', 'items': [{'parts': [
            {'text': 'Work then ', 'evidence_ids': [], 'scope': 'single_exchange'},
            {'text': 'Work', 'evidence_ids': ['a'], 'scope': 'single_exchange'},
            {'text': ' again.', 'evidence_ids': [], 'scope': 'single_exchange'}]}]}]}
        assembled = assemble_brief_parts(response)
        item = assembled['sections'][0]['items'][0]
        self.assertEqual(item['text'], 'Work then Work again.')
        self.assertEqual(item['claims'][0]['occurrence'], 1)
        self.assertFalse(validate_pre_session_response(assembled, self.evidence))

    def test_parts_cannot_merge_claim_with_neighboring_words(self):
        response = {'sections': [{'title': 'Active focus', 'items': [{'parts': [
            {'text': 'Reports', 'evidence_ids': [], 'scope': 'single_exchange'},
            {'text': 'overwork', 'evidence_ids': ['a'], 'scope': 'single_exchange'},
            {'text': 'again.', 'evidence_ids': [], 'scope': 'single_exchange'}]}]}]}
        assembled = assemble_brief_parts(response)
        self.assertEqual(assembled['sections'][0]['items'][0]['text'], 'Reports overwork again.')
        self.assertFalse(validate_pre_session_response(assembled, self.evidence))
