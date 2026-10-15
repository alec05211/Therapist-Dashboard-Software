import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from database import synthesis_refresh


class SynthesisRefreshQueueTests(unittest.TestCase):
    def connection(self, returned=None):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = returned
        return connection, cursor

    def test_enqueue_advances_revision_and_appends_auditable_event(self):
        connection, cursor = self.connection({"desired_insights_revision": 4})
        organization_id, client_id, actor_id, target_id = [str(uuid4()) for _ in range(4)]

        revision = synthesis_refresh.enqueue_insights_refresh(
            connection,
            organization_id=organization_id,
            client_id=client_id,
            event_type="evidence_claim_dismissed",
            actor_user_id=actor_id,
            target_type="client_journey_entry",
            target_id=target_id,
            metadata={"category": "theme"},
        )

        self.assertEqual(revision, 4)
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("clinical_synthesis_refresh_state" in sql for sql in statements))
        self.assertTrue(any("clinical_synthesis_refresh_events" in sql for sql in statements))
        state_call = next(call for call in cursor.execute.call_args_list
                          if "INSERT INTO app.clinical_synthesis_refresh_state" in call.args[0])
        self.assertIn("pending_event_count + 1", state_call.args[0])

    def test_enqueue_rejects_unknown_clinical_event(self):
        connection, _ = self.connection()
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            synthesis_refresh.enqueue_insights_refresh(
                connection,
                organization_id=str(uuid4()),
                client_id=str(uuid4()),
                event_type="page_viewed",
            )

    def test_claim_uses_skip_locked_worker_lease(self):
        work = {
            "organization_id": uuid4(),
            "client_id": uuid4(),
            "processing_insights_revision": 3,
        }
        connection, cursor = self.connection(work)
        claimed = synthesis_refresh.claim_due_insights_refresh(connection, worker_token="worker-a")
        self.assertEqual(claimed, work)
        self.assertIn("FOR UPDATE SKIP LOCKED", cursor.execute.call_args.args[0])

    def test_completion_queues_next_appointment_brief(self):
        connection, cursor = self.connection({
            "desired_insights_revision": 2,
            "processing_insights_revision": 2,
        })
        synthesis_refresh.complete_insights_refresh(
            connection,
            organization_id=str(uuid4()),
            client_id=str(uuid4()),
            worker_token="worker-a",
            published_revision=2,
            insight_snapshot_id=str(uuid4()),
        )
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("pre_session_brief_refresh_state" in sql for sql in statements))
        self.assertTrue(any("appointment.status IN ('scheduled', 'confirmed')" in sql for sql in statements))

    def test_scheduling_queues_brief_only_from_published_insights(self):
        connection, cursor = self.connection({"appointment_id": uuid4()})
        self.assertTrue(synthesis_refresh.enqueue_next_appointment_brief(
            connection,
            organization_id=str(uuid4()),
            client_id=str(uuid4()),
        ))
        statement = cursor.execute.call_args.args[0]
        self.assertIn("published_insight_snapshot_id IS NOT NULL", statement)
        self.assertIn("published_insights_revision > 0", statement)

    def test_reconciliation_only_repairs_revision_drift_or_expired_leases(self):
        connection, cursor = self.connection()
        cursor.rowcount = 2
        self.assertEqual(synthesis_refresh.reconcile_refresh_queue(connection), 2)
        statement = cursor.execute.call_args.args[0]
        self.assertIn("desired_insights_revision > published_insights_revision", statement)
        self.assertIn("lease_expires_at < CURRENT_TIMESTAMP", statement)

    def test_atomic_bundle_publication_advances_both_pointers(self):
        connection, cursor = self.connection({
            "desired_insights_revision": 4,
            "processing_insights_revision": 4,
        })
        synthesis_refresh.complete_synthesis_bundle(
            connection,
            organization_id=str(uuid4()),
            client_id=str(uuid4()),
            worker_token="worker-a",
            published_revision=4,
            insight_snapshot_id=str(uuid4()),
            appointment_id=str(uuid4()),
            brief_snapshot_id=str(uuid4()),
        )
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("published_insight_snapshot_id" in sql for sql in statements))
        self.assertTrue(any("published_brief_snapshot_id" in sql for sql in statements))
        self.assertTrue(any("status = 'superseded'" in sql for sql in statements))

    def test_high_value_review_event_is_due_immediately(self):
        connection, cursor = self.connection({"desired_insights_revision": 1})
        synthesis_refresh.enqueue_insights_refresh(
            connection,
            organization_id=str(uuid4()),
            client_id=str(uuid4()),
            event_type="evidence_claim_accepted",
        )
        state_call = next(call for call in cursor.execute.call_args_list
                          if "INSERT INTO app.clinical_synthesis_refresh_state" in call.args[0])
        self.assertEqual(state_call.args[1][2], 0)


if __name__ == "__main__":
    unittest.main()
