import unittest

from unittest.mock import patch
from ai_harness.longitudinal_insights import generate_openai_longitudinal_insights, to_snapshot_content, validate_response
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
        return {'overview': 'A cautious overview.', 'section_summaries': [{'kind': 'open_thread', 'summary': 'An emerging shift remains an open question for review.'}], 'items': [{
            'kind': 'open_thread', 'label': 'A possible shift',
            'analysis': 'This may reflect greater tolerance of uncertainty, although persistence remains unclear.',
            'analysis_claims': [{'phrase': 'greater tolerance of uncertainty', 'occurrence': 0,
                                 'evidence_ids': ['e-1', 'e-2']}],
            'context_statements': [],
        }]}

    def test_analytical_phrase_can_link_to_multiple_records_without_repetitive_context(self):
        document = self.analytical_document()
        self.assertEqual(validate_response(document, self.evidence, set(), require_analysis_claims=True), [])
        _, items = to_snapshot_content(document)
        self.assertEqual(items[0]['evidence_ids'], ['e-1', 'e-2'])
        InsightItem(item_kind='open_thread', content=items[0]['content'], evidence=(
            InsightEvidence(transcript_segment_id='e-1'),
            InsightEvidence(clinical_note_version_id='e-2'),
        )).validate()

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
        self.assertEqual(payload['text']['format']['schema']['properties']['items']['minItems'], 1)

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
        document['section_summaries'][0]['summary'] = 'x' * 281
        self.assertIn('280 characters', '; '.join(validate_response(document, self.evidence, set())))

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
