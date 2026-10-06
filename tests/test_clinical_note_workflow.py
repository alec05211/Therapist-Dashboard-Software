import unittest
from unittest.mock import patch

import server


class ClinicalNoteWorkflowTests(unittest.TestCase):
    def test_latest_note_read_is_client_scoped(self):
        latest = {"id": "note-1", "status": "draft", "content": {"plain_text": "Draft"}}
        with patch.object(server, "connect"), patch.object(server, "authorize_clinical_access") as authorize, patch.object(
            server.LongitudinalRecordRepository, "get_latest_clinical_note_version", return_value=latest
        ) as read:
            result = server.get_latest_clinical_note_version("client-1", "org-1", "session-1", "Bearer therapist")

        self.assertEqual(result, {"note": latest})
        self.assertFalse(authorize.call_args.kwargs["require_write"])
        self.assertEqual(read.call_args.kwargs["session_id"], "session-1")

    def test_autosave_uses_one_working_draft_boundary(self):
        saved = {"id": "note-1", "status": "draft", "version_number": 1, "parent_version_id": None}
        request = server.ClinicalNoteDraftRequest(
            organization_id="org-1",
            session_id="session-1",
            content={"schema_version": 1, "plain_text": "Edited", "document": {"type": "doc"}},
        )
        with patch.object(server, "connect") as connect, patch.object(server, "authorize_clinical_access", return_value="user-1"), patch.object(
            server.LongitudinalRecordRepository, "save_clinical_note_draft", return_value=saved
        ) as save:
            result = server.save_clinical_note_draft("client-1", request, "Bearer therapist")

        self.assertEqual(result, saved)
        self.assertEqual(save.call_args.kwargs["actor_user_id"], "user-1")
        connect.return_value.__enter__.return_value.commit.assert_called_once()

    def test_finalization_queues_amendment_refresh(self):
        finalized = {"id": "note-2", "status": "finalized", "parent_version_id": "note-1", "finalized_at": "now"}
        request = server.ClinicalNoteFinalizeRequest(organization_id="org-1", session_id="session-1")
        with patch.object(server, "connect") as connect, patch.object(server, "authorize_clinical_access", return_value="user-1"), patch.object(
            server.LongitudinalRecordRepository, "finalize_clinical_note_draft", return_value=finalized
        ), patch.object(server.synthesis_refresh, "enqueue_insights_refresh") as enqueue:
            result = server.finalize_clinical_note_draft("client-1", "note-2", request, "Bearer therapist")

        self.assertEqual(result, finalized)
        self.assertEqual(enqueue.call_args.kwargs["event_type"], "clinical_note_amended")
        self.assertEqual(enqueue.call_args.kwargs["target_id"], "note-2")
        connect.return_value.__enter__.return_value.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
