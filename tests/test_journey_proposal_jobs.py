import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from database import journey_proposal_jobs


class JourneyProposalJobTests(unittest.TestCase):
    def test_missing_provider_configuration_blocks_without_querying_client(self):
        cursor = MagicMock()
        job = {'client_id': uuid4()}
        with patch.dict(journey_proposal_jobs.os.environ, {
                'OPENAI_API_KEY': '',
                'JOURNEY_PROPOSAL_MODEL': '',
                'PRE_SESSION_MODEL': '',
        }, clear=False):
            self.assertEqual(journey_proposal_jobs._policy(cursor, job),
                             (None, None, 'model_configuration_missing'))
        cursor.execute.assert_not_called()

    def test_configured_provider_allows_any_client_without_eligibility_query(self):
        cursor = MagicMock()
        with patch.dict(journey_proposal_jobs.os.environ, {
                'OPENAI_API_KEY': 'test-key',
                'JOURNEY_PROPOSAL_MODEL': 'test-model',
        }, clear=False):
            self.assertEqual(journey_proposal_jobs._policy(
                cursor, {'client_id': uuid4()}), ('test-key', 'test-model', None))
        cursor.execute.assert_not_called()

    def test_model_failure_is_recorded_without_raising_into_ingestion(self):
        job = {
            'session_id': uuid4(), 'organization_id': uuid4(), 'client_id': uuid4(),
            'source_transcript_version_id': uuid4(), 'worker_token': 'lease',
            'attempt_count': 1, 'api_key': 'test-key', 'model': 'test-model',
        }
        with patch.object(journey_proposal_jobs, '_claim_job', return_value=job), \
                patch.object(journey_proposal_jobs, '_input_bundle',
                             return_value=([{'segment_key': '0'}], None, 'fingerprint')), \
                patch.object(journey_proposal_jobs, 'discover_openai_evidence_claims',
                             side_effect=RuntimeError('provider unavailable')), \
                patch.object(journey_proposal_jobs, '_fail') as fail:
            self.assertTrue(journey_proposal_jobs.process_one(session_id=job['session_id']))
        fail.assert_called_once_with(job, 'RuntimeError')


if __name__ == '__main__':
    unittest.main()
