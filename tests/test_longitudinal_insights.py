import unittest

from unittest.mock import patch
from ai_harness.longitudinal_insights import (
    canonicalize_response_anchors,
    generate_openai_longitudinal_insights,
    materialize_response_anchors,
    to_snapshot_content,
    validate_response,
)
from database.longitudinal_records import InsightEvidence, InsightItem


class LongitudinalInsightHarnessTests(unittest.TestCase):
    def setUp(self):
        self.evidence = [{"evidence_id": f"e-{index}"} for index in range(1, 5)]
        self.generated = {
            "overview": "A cautious overview.",
            "items": [
                {
                    "kind": kind,
                    "label": f"Review area {index}",
                    "analysis": f"A possible area {index} to review.",
                    "context_statements": [{
                        "text": "Across the record, the client described a specific moment and named its effect.",
                        "claims": [{
                            "phrase": "the client described a specific moment",
                            "occurrence": 0,
                            "evidence_ids": [f"e-{index}"],
                        }, {
                            "phrase": "named its effect",
                            "occurrence": 0,
                            "evidence_ids": [f"e-{index}"],
                        }],
                    }],
                }
                for index, kind in enumerate(("trajectory", "theme", "open_thread", "relevant_history"), 1)
            ],
        }

    def test_accepts_separate_analysis_and_contextual_evidence(self):
        self.assertEqual(validate_response(self.generated, self.evidence), [])

    def test_rejects_unavailable_context_evidence(self):
        self.generated["items"][0]["context_statements"][0]["claims"][0]["evidence_ids"] = ["missing"]
        self.assertIn("cites unavailable evidence", "; ".join(validate_response(self.generated, self.evidence)))

    def test_projects_links_only_into_context_statements(self):
        summary, items = to_snapshot_content(self.generated)
        self.assertEqual(summary["text"], "A cautious overview.")
        self.assertNotIn("claims", items[0]["content"])
        self.assertEqual(items[0]["content"]["label"], "Review area 1")
        context = items[0]["content"]["contexts"][0]
        self.assertEqual(context["claims"][0]["phrase"], "the client described a specific moment")
        self.assertEqual(context["claims"][1]["phrase"], "named its effect")

    def analytical_document(self):
        return {'overview': 'A cautious overview.', 'section_summaries': [{'kind': 'open_thread', 'summary': 'An emerging shift remains an open question for review.', 'topic_coverage': [{'topic_index': 0, 'phrase': 'An emerging shift'}]}], 'items': [{
            'kind': 'open_thread', 'label': 'A possible shift',
            'analysis': 'This may reflect greater tolerance of uncertainty, although persistence remains unclear.',
            'analysis_claims': [{'phrase': 'greater tolerance of uncertainty', 'occurrence': 0,
                                 'evidence_ids': ['e-1', 'e-2']}],
            'context_statements': [],
            'evidence_roles': [
                {'evidence_id': 'e-1', 'role': 'supporting'},
                {'evidence_id': 'e-2', 'role': 'contrasting'},
            ],
        }]}

    def test_analytical_phrase_can_link_to_multiple_records_without_repetitive_context(self):
        document = self.analytical_document()
        self.assertEqual(validate_response(document, self.evidence, set(), require_analysis_claims=True), [])
        _, items = to_snapshot_content(document)
        self.assertEqual(items[0]['evidence_ids'], ['e-1', 'e-2'])
        self.assertEqual(items[0]['evidence_roles'], {'e-1': 'supporting', 'e-2': 'contrasting'})
        InsightItem(item_kind='open_thread', content=items[0]['content'], evidence=(
            InsightEvidence(transcript_segment_id='e-1'),
            InsightEvidence(clinical_note_version_id='e-2'),
        )).validate()

    def test_evidence_roles_must_cover_citations_exactly_once(self):
        document = self.analytical_document()
        self.assertEqual(validate_response(
            document, self.evidence, set(), require_evidence_roles=True), [])
        document['items'][0]['evidence_roles'].pop()
        self.assertIn('cover every cited source exactly once', '; '.join(validate_response(
            document, self.evidence, set(), require_evidence_roles=True)))

    def test_missing_or_unavailable_analytical_support_is_rejected(self):
        document = self.analytical_document()
        document['items'][0]['analysis_claims'][0]['evidence_ids'] = ['pending-proposal']
        self.assertIn('unavailable evidence', '; '.join(validate_response(document, self.evidence, set())))
        del document['items'][0]['analysis_claims']
        self.assertIn('analytical evidence anchors', '; '.join(validate_response(
            document, self.evidence, set(), require_analysis_claims=True)))

    def test_analytical_phrase_must_exist_and_anchors_must_not_overlap(self):
        document = self.analytical_document()
        claim = document['items'][0]['analysis_claims'][0]
        claim['phrase'] = 'missing phrase'
        self.assertIn('phrase is absent', '; '.join(validate_response(document, self.evidence, set())))
        claim['phrase'] = 'greater tolerance of uncertainty'
        document['items'][0]['analysis_claims'].append(dict(claim))
        self.assertIn('overlapping', '; '.join(validate_response(document, self.evidence, set())))

    def test_formatting_equivalent_anchor_is_canonicalized_to_exact_prose(self):
        document = self.analytical_document()
        document['items'][0]['analysis'] = "Owen’s plan may remain\nunfinished."
        claim = document['items'][0]['analysis_claims'][0]
        claim.update(phrase="owen's plan may remain unfinished.", occurrence=0)
        canonicalize_response_anchors(document)
        self.assertEqual(claim['phrase'], "Owen’s plan may remain\nunfinished.")
        self.assertEqual(validate_response(
            document, self.evidence, set(), require_evidence_roles=True), [])

    def test_non_equivalent_anchor_is_not_relocated_or_invented(self):
        document = self.analytical_document()
        claim = document['items'][0]['analysis_claims'][0]
        claim['phrase'] = 'a different clinical interpretation'
        canonicalize_response_anchors(document)
        self.assertEqual(claim['phrase'], 'a different clinical interpretation')
        self.assertIn('phrase is absent', '; '.join(validate_response(document, self.evidence, set())))

    def test_sentence_index_materializes_an_exact_persisted_anchor(self):
        document = self.analytical_document()
        document['items'][0]['analysis'] = (
            'This may reflect greater tolerance of uncertainty. '
            'Persistence remains unclear.'
        )
        claim = document['items'][0]['analysis_claims'][0]
        claim.clear()
        claim.update(sentence_index=1, evidence_ids=['e-1', 'e-2'])
        materialize_response_anchors(document)
        self.assertEqual(claim['phrase'], 'Persistence remains unclear.')
        self.assertEqual(claim['occurrence'], 0)
        _, items = to_snapshot_content(document)
        self.assertNotIn('sentence_index', items[0]['content']['analysis_claims'][0])

    def test_summary_sentence_index_materializes_exact_coverage_phrase(self):
        document = self.analytical_document()
        coverage = document['section_summaries'][0]['topic_coverage'][0]
        coverage.clear()
        coverage.update(topic_index=0, sentence_index=0)
        materialize_response_anchors(document)
        self.assertEqual(
            coverage['phrase'],
            'An emerging shift remains an open question for review.',
        )
        self.assertEqual(validate_response(
            document, self.evidence, set(), require_summary_coverage=True), [])

    def test_identical_analyses_across_sections_are_rejected(self):
        document = self.analytical_document()
        document['items'].append({**document['items'][0], 'kind': 'theme'})
        self.assertIn('consolidate across sections', '; '.join(validate_response(document, self.evidence, set())))

    def test_generation_coordinates_sections_in_one_request_without_filling_quotas(self):
        with patch('ai_harness.longitudinal_insights._request_structured_response',
                   return_value=(self.analytical_document(), {})) as request:
            generate_openai_longitudinal_insights(evidence=self.evidence, api_key='test', model='test')
        request.assert_called_once()
        payload = request.call_args.args[0]
        self.assertIn('Plan trajectory, theme, open_thread, and relevant_history together', payload['instructions'])
        self.assertIn('Do not repeat an interpretation', payload['instructions'])
        self.assertIn('Classify roles relative to the direction', payload['instructions'])
        self.assertIn('Do not manufacture contrasting evidence', payload['instructions'])
        self.assertEqual(payload['text']['format']['schema']['properties']['items']['minItems'], 1)

    def test_themes_have_no_count_or_summary_coverage_ceiling(self):
        from copy import deepcopy
        from ai_harness.longitudinal_insights import response_schema
        document = self.analytical_document()
        template = document['items'][0]
        document['items'] = []
        coverage = []
        for index in range(14):
            item = deepcopy(template)
            item.update(kind='theme', label=f'Pattern {index}',
                        analysis=f'Pattern {index} may show greater tolerance of uncertainty.')
            document['items'].append(item)
            coverage.append({'topic_index': index, 'phrase': f'Pattern {index}'})
        document['section_summaries'] = [{'kind': 'theme',
            'summary': '; '.join(entry['phrase'] for entry in coverage), 'topic_coverage': coverage}]
        self.assertEqual(validate_response(document, self.evidence, set(),
                         require_analysis_claims=True, require_section_summaries=True,
                         require_summary_coverage=True), [])
        schema = response_schema({'theme'})['properties']
        self.assertNotIn('maxItems', schema['items'])
        self.assertNotIn('maxItems', schema['section_summaries']['items']['properties']['topic_coverage'])
        document['items'].append({**document['items'][0], 'label': ' PATTERN 0! ', 'analysis': 'Different prose for the same named pattern.'})
        self.assertIn("duplicates another theme's label", '; '.join(validate_response(document, self.evidence, set())))

    def test_all_sections_allow_more_than_two_distinct_items(self):
        from ai_harness.longitudinal_insights import response_schema
        for kind in ('trajectory', 'theme', 'open_thread', 'relevant_history'):
            with self.subTest(kind=kind):
                document = self.analytical_document()
                template = document['items'][0]
                document['items'] = [{**template, 'kind': kind, 'label': f'Focus {index}',
                    'analysis': f'Observation {index} may suggest greater tolerance of uncertainty.'}
                    for index in range(15)]
                coverage = [{'topic_index': index, 'phrase': f'Focus {index}'} for index in range(15)]
                document['section_summaries'] = [{'kind': kind,
                    'summary': '; '.join(entry['phrase'] for entry in coverage), 'topic_coverage': coverage}]
                self.assertEqual(validate_response(document, self.evidence, set(),
                    require_analysis_claims=True, require_section_summaries=True,
                    require_summary_coverage=True), [])
                schema = response_schema({kind})['properties']
                self.assertNotIn('maxItems', schema['items'])
                self.assertNotIn('maxItems', schema['section_summaries']['items']['properties']['topic_coverage'])
                _, items = to_snapshot_content(document)
                self.assertEqual(len(items), 15)
        coverage_schema = response_schema()['properties']['section_summaries']['items']['properties']['topic_coverage']
        self.assertNotIn('maximum', coverage_schema['items']['properties']['topic_index'])

    def test_section_summaries_are_persisted_without_copying_topic_prose(self):
        document = self.analytical_document()
        self.assertEqual(validate_response(document, self.evidence, set(), require_section_summaries=True), [])
        content, _ = to_snapshot_content(document)
        self.assertEqual(content['section_summaries']['open_thread'], document['section_summaries'][0]['summary'])
        document['section_summaries'][0]['summary'] = document['items'][0]['analysis']
        self.assertIn('copies topic prose', '; '.join(validate_response(document, self.evidence, set())))

    def test_section_summaries_cover_only_populated_kinds_once(self):
        document = self.analytical_document()
        for summaries in ([], [{'kind': 'theme', 'summary': 'A different topic.'}], document['section_summaries'] * 2):
            document['section_summaries'] = summaries
            self.assertIn('exactly once', '; '.join(validate_response(document, self.evidence, set(), require_section_summaries=True)))
        document.pop('section_summaries')
        self.assertIn('must be a list', '; '.join(validate_response(document, self.evidence, set(), require_section_summaries=True)))

    def test_section_summary_length_is_bounded(self):
        document = self.analytical_document()
        document['section_summaries'][0]['summary'] = 'x' * 601
        self.assertIn('600 characters', '; '.join(validate_response(document, self.evidence, set())))

    def test_multi_topic_summary_requires_meaningful_phrase_for_every_topic(self):
        document = self.analytical_document()
        document['items'].append({**document['items'][0], 'label': 'Receiving care',
                                 'analysis': 'Receiving help may still feel unfamiliar.',
                                 'analysis_claims': [{'phrase': 'Receiving help', 'occurrence': 0, 'evidence_ids': ['e-1']}],
                                 'evidence_roles': [{'evidence_id': 'e-1', 'role': 'supporting'}]})
        section = document['section_summaries'][0]
        self.assertIn('each of its topics', '; '.join(validate_response(
            document, self.evidence, set(), require_summary_coverage=True)))
        section['summary'] += ' Receiving support remains unfamiliar alongside that change.'
        section['topic_coverage'].append({'topic_index': 1, 'phrase': 'Receiving support remains unfamiliar'})
        self.assertEqual(validate_response(document, self.evidence, set(), require_summary_coverage=True), [])
        section['topic_coverage'][1]['phrase'] = 'A phrase that is absent'
        self.assertIn('coverage phrase is absent', '; '.join(validate_response(
            document, self.evidence, set(), require_summary_coverage=True)))

    def test_summary_cannot_reuse_one_phrase_to_hide_a_second_topic(self):
        document = self.analytical_document()
        document['items'].append({**document['items'][0], 'label': 'A second topic'})
        document['section_summaries'][0]['topic_coverage'].append({'topic_index': 1, 'phrase': 'An emerging shift'})
        self.assertIn('reuses the same explanation', '; '.join(validate_response(
            document, self.evidence, set(), require_summary_coverage=True)))

    def test_summary_cannot_claim_coverage_of_a_different_section(self):
        document = self.analytical_document()
        document['items'].append({**document['items'][0], 'kind': 'theme', 'analysis': 'A separate interpretation.'})
        document['section_summaries'][0]['topic_coverage'].append({'topic_index': 1, 'phrase': 'An emerging shift'})
        self.assertIn('each of its topics', '; '.join(validate_response(
            document, self.evidence, set(), require_summary_coverage=True)))

    def test_duplicate_document_is_repaired_with_all_sections_in_context(self):
        document = self.analytical_document()
        duplicate = {**document, 'items': [document['items'][0], {**document['items'][0], 'kind': 'theme'}]}
        with patch('ai_harness.longitudinal_insights._request_structured_response',
                   side_effect=[(duplicate, {}), (document, {})]) as request:
            generate_openai_longitudinal_insights(evidence=self.evidence, api_key='test', model='test')
        import json
        repair = json.loads(request.call_args.args[0]['input'])
        self.assertEqual(len(repair['rejected_draft']['items']), 2)
        self.assertEqual(repair['evidence'], self.evidence)


if __name__ == "__main__":
    unittest.main()
