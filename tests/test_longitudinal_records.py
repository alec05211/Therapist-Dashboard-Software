import unittest

from database.longitudinal_records import InsightEvidence, InsightItem


class InsightClaimValidationTests(unittest.TestCase):
    def item(self, claims):
        return InsightItem(
            item_kind="trajectory",
            content={"text": "A supported statement.", "claims": claims},
            evidence=(InsightEvidence(transcript_segment_id="segment-1"),),
        )

    def test_accepts_explicit_claim_anchor_for_attached_evidence(self):
        self.item([{
            "phrase": "supported statement",
            "occurrence": 0,
            "evidence_ids": ["segment-1"],
        }]).validate()

    def test_rejects_claim_anchor_for_unattached_evidence(self):
        with self.assertRaisesRegex(ValueError, "attached to the item"):
            self.item([{
                "phrase": "supported statement",
                "occurrence": 0,
                "evidence_ids": ["segment-2"],
            }]).validate()

    def test_rejects_invalid_claim_occurrence(self):
        with self.assertRaisesRegex(ValueError, "non-negative integers"):
            self.item([{
                "phrase": "supported statement",
                "occurrence": -1,
                "evidence_ids": ["segment-1"],
            }]).validate()

    def test_accepts_claims_only_in_contextual_evidence_layer(self):
        InsightItem(
            item_kind="theme",
            content={
                "analysis": "A possible theme to review.",
                "contexts": [{
                    "text": "This was visible when a specific moment occurred.",
                    "claims": [{
                        "phrase": "a specific moment occurred",
                        "occurrence": 0,
                        "evidence_ids": ["segment-1"],
                    }],
                }],
            },
            evidence=(InsightEvidence(transcript_segment_id="segment-1"),),
        ).validate()

    def test_rejects_context_claim_phrase_missing_from_context(self):
        with self.assertRaisesRegex(ValueError, "occur in their contextual text"):
            InsightItem(
                item_kind="theme",
                content={
                    "analysis": "A possible theme to review.",
                    "contexts": [{
                        "text": "This was visible in one moment.",
                        "claims": [{
                            "phrase": "a different phrase",
                            "occurrence": 0,
                            "evidence_ids": ["segment-1"],
                        }],
                    }],
                },
                evidence=(InsightEvidence(transcript_segment_id="segment-1"),),
            ).validate()


if __name__ == "__main__":
    unittest.main()
