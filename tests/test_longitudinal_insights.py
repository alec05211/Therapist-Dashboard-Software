import unittest

from ai_harness.longitudinal_insights import to_snapshot_content, validate_response


class LongitudinalInsightHarnessTests(unittest.TestCase):
    def setUp(self):
        self.evidence = [{"evidence_id": f"e-{index}"} for index in range(1, 5)]
        self.generated = {
            "overview": "A cautious overview.",
            "items": [
                {
                    "kind": kind,
                    "label": f"Review area {index}",
                    "analysis": "A possible area to review.",
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


if __name__ == "__main__":
    unittest.main()
