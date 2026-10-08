import unittest
from unittest.mock import patch

from ai_harness.journey_proposals import (
    discover_openai_evidence_claims,
    validate_discovered_claims,
    validate_proposal_analysis,
)


class JourneyProposalAnalysisTests(unittest.TestCase):
    def test_accepts_multi_category_source_bounded_analysis(self):
        generated = {"proposals": [{
            "proposal_key": "0:HISTORY:0",
            "categories": ["theme", "open_thread"],
            "synthesis_focus": "This may be useful to compare with the existing work-boundary pattern.",
            "relationship": "reinforces",
            "related_insight_item_ids": ["insight-1"],
        }]}
        self.assertEqual(validate_proposal_analysis(
            generated,
            proposal_keys=["0:HISTORY:0"],
            insight_item_ids=["insight-1"],
        ), [])

    def test_rejects_longitudinal_claim_without_related_insight(self):
        generated = {"proposals": [{
            "proposal_key": "0:HISTORY:0",
            "categories": ["theme"],
            "synthesis_focus": "A possible pattern to compare.",
            "relationship": "reinforces",
            "related_insight_item_ids": [],
        }]}
        violations = validate_proposal_analysis(
            generated,
            proposal_keys=["0:HISTORY:0"],
            insight_item_ids=["insight-1"],
        )
        self.assertIn("needs related Insights context", "; ".join(violations))

    def test_rejects_missing_or_duplicate_proposals(self):
        generated = {"proposals": [{
            "proposal_key": "0:HISTORY:0",
            "categories": ["context", "context"],
            "synthesis_focus": "Context to preserve.",
            "relationship": "session_context",
            "related_insight_item_ids": [],
        }]}
        violations = validate_proposal_analysis(
            generated,
            proposal_keys=["0:HISTORY:0", "0:HISTORY:1"],
            insight_item_ids=[],
        )
        self.assertIn("invalid categories", "; ".join(violations))
        self.assertIn("exactly one result", "; ".join(violations))

    def test_full_transcript_claims_require_known_evidence_and_safe_categories(self):
        generated = {'claims': [{
            'claim_summary': 'The client named a change.',
            'evidence_segment_keys': ['4'],
            'categories': ['breakthrough', 'important_quote'],
            'synthesis_focus': 'Preserve the client’s newly stated understanding.',
            'relationship': 'session_context',
            'related_insight_item_ids': [],
        }]}
        self.assertEqual(validate_discovered_claims(
            generated, segment_keys=['3', '4'], insight_item_ids=[]), [])
        generated['claims'][0]['evidence_segment_keys'] = ['missing']
        self.assertIn('claim 0 has invalid transcript evidence', validate_discovered_claims(
            generated, segment_keys=['3', '4'], insight_item_ids=[]))

    @patch('ai_harness.journey_proposals._request_structured_response')
    def test_first_session_downgrades_uncited_longitudinal_relationship(self, request):
        request.return_value = ({'claims': [{
            'claim_summary': 'The client named a change.',
            'evidence_segment_keys': ['0'],
            'categories': ['breakthrough', 'important_quote'],
            'synthesis_focus': 'Preserve the client’s newly stated understanding.',
            'relationship': 'reinforces',
            'related_insight_item_ids': [],
        }]}, {'model': 'test-model', 'id': 'response-1', 'usage': {}})

        claims, _ = discover_openai_evidence_claims(
            segments=[{'segment_key': '0', 'text': 'I see this differently now.'}],
            insights_context=None, api_key='test-key', model='test-model')

        self.assertEqual(claims[0]['relationship'], 'session_context')
        self.assertEqual(claims[0]['categories'], ['important_quote', 'breakthrough'])


if __name__ == "__main__":
    unittest.main()
