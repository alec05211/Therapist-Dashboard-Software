import os
import unittest
from unittest.mock import patch

import server


class ClinicalSynthesisWorkerRuntimeTests(unittest.TestCase):
    def test_provider_configuration_enables_all_client_queue_processing(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "configured",
                "INSIGHTS_MODEL": "insights-model",
                "PRE_SESSION_MODEL": "brief-model",
            },
            clear=True,
        ):
            self.assertTrue(server.clinical_synthesis_worker_configured())

    def test_deployment_can_pause_worker_without_a_client_allowlist(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "configured",
                "INSIGHTS_MODEL": "insights-model",
                "PRE_SESSION_MODEL": "brief-model",
                "CLINICAL_SYNTHESIS_WORKER_ENABLED": "false",
            },
            clear=True,
        ):
            self.assertFalse(server.clinical_synthesis_worker_configured())

    def test_missing_provider_configuration_keeps_worker_stopped(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(server.clinical_synthesis_worker_configured())


if __name__ == "__main__":
    unittest.main()
