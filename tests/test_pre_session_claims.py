import copy
import json
from unittest.mock import MagicMock, patch
import unittest
from ai_harness.pre_session import (MAX_BRIEF_REQUEST_BYTES,
    generate_openai_pre_session_brief, resolve_brief, validate_pre_session_response)
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

    def test_oversized_note_payload_keeps_cross_session_citations_resolvable(self):
        sources = [
            {'evidence_id': source_id, 'session_id': session, 'clinical_note_version_id': source_id,
             'note_text': 'Full finalized note. ' * 4000}
            for source_id, session in [('a', 'one'), ('b', 'two')]
        ]
        _, request = brief_input({'sections': [{'items': [
            {'text': 'The record describes staying late in two sessions.', 'sources': sources},
        ]}]})
        prose = {'sections': [{'title': 'Important trajectory', 'items': [{
            'text': 'The record describes staying late in two sessions.',
            'evidence_ids': ['a', 'b'],
        }]}]}
        annotations = {'annotations': [{
            'item_index': 0, 'phrase': 'staying late', 'occurrence': 0,
            'scope': 'cross_session', 'evidence_ids': ['a', 'b'],
        }]}
        with patch('ai_harness.pre_session.urlopen', side_effect=[
            self.provider_response(prose), self.provider_response(annotations),
        ]) as urlopen:
            generated, _ = generate_openai_pre_session_brief(
                synthesis_request=request, api_key='test', model='test')
        for call in urlopen.call_args_list:
            data = call.args[0].data
            self.assertLessEqual(len(data), MAX_BRIEF_REQUEST_BYTES)
            model_input = json.loads(json.loads(data)['input'])
            self.assertEqual([source['evidence_id'] for source in model_input['evidence']], ['a', 'b'])
            self.assertTrue(all('note_text' not in source for source in model_input['evidence']))
        item = resolve_brief(generated, request['evidence'])['sections'][0]['items'][0]
        self.assertEqual(item['claims'][0]['sources'], sources)

    @staticmethod
    def provider_response(output):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'output_text': json.dumps(output), 'usage': {'input_tokens': 100, 'output_tokens': 50},
        }).encode()
        return response

    def test_annotation_repair_preserves_prose_and_limits_evidence_to_selected_items(self):
        _, request = brief_input({'sections': [{'items': [
            {'text': 'Work pressure remained important.', 'sources': [source]}
            for source in self.evidence
        ]}]})
        text = 'Work pressure eased, though Work pressure still came up.'
        prose = {'sections': [{'title': 'Important trajectory', 'items': [{
            'text': text, 'evidence_ids': ['a'],
        }]}]}
        annotation = {
            'item_index': 0, 'phrase': 'Work pressure', 'occurrence': 1,
            'scope': 'single_exchange', 'evidence_ids': ['a'],
        }
        invalid = {'annotations': [{**annotation, 'evidence_ids': ['b']}]}
        too_long = {'annotations': [{**annotation, 'phrase': 'Work pressure eased, though Work',
                                     'occurrence': 0}]}
        valid = {'annotations': [annotation]}
        repairs = []
        with patch('ai_harness.pre_session.urlopen', side_effect=[
            self.provider_response(output) for output in (prose, invalid, too_long, valid)
        ]) as urlopen:
            generated, metadata = generate_openai_pre_session_brief(
                synthesis_request=request, api_key='test', model='test',
                on_repair=lambda attempt, count: repairs.append((attempt, count)),
            )
        self.assertEqual(urlopen.call_count, 4)
        self.assertEqual(repairs, [(1, 1), (2, 1)])
        item = generated['sections'][0]['items'][0]
        self.assertEqual(item['text'], text)
        self.assertEqual(item['claims'][0]['occurrence'], 1)
        self.assertEqual(metadata['usage'], {'input_tokens': 400, 'output_tokens': 200})
        for call in urlopen.call_args_list[1:]:
            annotation_input = json.loads(json.loads(call.args[0].data)['input'])
            self.assertEqual(annotation_input['task'], 'annotate_pre_session_brief')
            self.assertEqual(annotation_input['items'][0]['text'], text)
            self.assertEqual(annotation_input['evidence'], [self.evidence[0]])

    def test_item_without_short_anchor_preserves_statement_evidence(self):
        _, request = brief_input({'sections': [{'items': [
            {'text': 'Work pressure remained important.', 'sources': [self.evidence[0]]},
        ]}]})
        prose = {'sections': [{'title': 'Important trajectory', 'items': [{
            'text': 'Work pressure remained important.', 'evidence_ids': ['a'],
        }]}]}
        with patch('ai_harness.pre_session.urlopen', side_effect=[
            self.provider_response(prose), self.provider_response({'annotations': []}),
        ]):
            generated, _ = generate_openai_pre_session_brief(
                synthesis_request=request, api_key='test', model='test')
        item = resolve_brief(generated, request['evidence'])['sections'][0]['items'][0]
        self.assertEqual(item['claims'], [])
        self.assertEqual(item['sources'], [self.evidence[0]])
