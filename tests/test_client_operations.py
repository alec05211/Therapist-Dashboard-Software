import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, HTTPException, Response
from psycopg import OperationalError

from database import client_operations as operations
from ai_harness import client_assistant_tools as tools


class ClientOperationsTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.context = {"organization_id": "org-a", "client_id": "client-a"}
        app = FastAPI()
        app.include_router(operations.router)
        self.app = app

    def test_identity_requires_exactly_one_active_link(self):
        with patch.object(operations, "validate_access_token", return_value={"sub": "subject"}):
            for rows in ([], [self.context, self.context]):
                self.cursor.fetchall.return_value = rows
                with self.assertRaises(HTTPException) as error:
                    operations.client_context(self.connection, "Bearer token")
                self.assertEqual(error.exception.status_code, 403)
            self.cursor.fetchall.return_value = [self.context]
            self.assertEqual(operations.client_context(self.connection, "Bearer token"), self.context)
        query, parameters = self.cursor.execute.call_args.args
        self.assertEqual(parameters, ("subject",))
        for condition in ("portal.status='active'", "client.status='active'", "organization.status='active'"):
            self.assertIn(condition, query)

    def test_scheduling_is_bounded_scoped_and_minimized(self):
        now = datetime.now(timezone.utc)
        self.cursor.fetchall.return_value = [{"starts_at": now, "ends_at": now,
            "status": "confirmed", "meeting_mode": "virtual", "private_note": "hidden"}] * 3
        result = operations.read_scheduling(self.connection, self.context, limit=2)
        self.assertEqual(len(result["appointments"]), 2)
        self.assertTrue(result["has_more"])
        self.assertNotIn("private_note", str(result))
        self.assertEqual(self.cursor.execute.call_args.args[1], ("org-a", "client-a", 3))
        self.cursor.fetchall.return_value = []
        self.assertEqual(operations.read_scheduling(self.connection, self.context)["appointments"], [])

    def test_billing_prefers_corrections_and_omits_identifiers(self):
        self.cursor.fetchone.return_value = {"status": "ready", "updated_at": datetime.now(timezone.utc),
            "model_extracted_fields": {"payer_name": "Old"},
            "client_corrected_fields": {"payer_name": "Corrected", "member_id": "secret", "member_name": "Private"}}
        result = operations.read_billing(self.connection, self.context)
        self.assertEqual(result["insurance"]["details"]["payer_name"], "Corrected")
        self.assertTrue(result["insurance"]["client_reviewed"])
        self.assertFalse(result["insurance"]["benefits_verified"])
        self.assertNotIn("secret", str(result))
        self.assertNotIn("Private", str(result))
        self.assertIsNone(result["billing"]["balance"])
        self.assertIsNone(result["billing"]["invoices"])
        self.assertEqual(self.cursor.execute.call_args.args[1], ("org-a", "client-a"))

    def test_missing_or_processing_insurance_never_exposes_extraction(self):
        self.cursor.fetchone.return_value = None
        self.assertEqual(operations.read_billing(self.connection, self.context)["insurance"]["status"], "not_on_file")
        self.cursor.fetchone.return_value = {"status": "failed", "updated_at": datetime.now(timezone.utc),
            "model_extracted_fields": {"payer_name": "Unusable"}}
        result = operations.read_billing(self.connection, self.context)
        self.assertEqual(result["insurance"]["status"], "unavailable")
        self.assertIsNone(result["insurance"]["details"])

    def test_route_bounds_auth_and_cache(self):
        route = next(route for route in operations.router.routes if route.path == "/client-operations/scheduling")
        limit_field = route.dependant.query_params[0]
        for value in (0, 21, "wrong"):
            _, errors = limit_field.validate(value, {}, loc=("query", "limit"))
            self.assertTrue(errors)
        with patch.object(operations, "authorized_read", return_value={"status": "available"}) as read:
            response = Response()
            operations.scheduling_information(response, limit=2, authorization="Bearer client")
            self.assertEqual(response.headers["cache-control"], "no-store")
            read.assert_called_once_with("Bearer client", operations.read_scheduling, limit=2)
            response = Response()
            operations.billing_information(response, authorization="Bearer client")
            self.assertEqual(response.headers["cache-control"], "no-store")
            read.assert_called_with("Bearer client", operations.read_billing)
        with patch.object(operations, "connect", return_value=self.connection), \
             patch.object(operations, "validate_access_token", side_effect=HTTPException(401, "Sign in")):
            with self.assertRaises(HTTPException) as error:
                operations.billing_information(Response(), authorization=None)
            self.assertEqual(error.exception.status_code, 401)

    def test_auth_failure_and_database_failure_do_not_become_empty_results(self):
        reader = MagicMock()
        with patch.object(operations, "connect", return_value=self.connection), \
             patch.object(operations, "client_context", side_effect=HTTPException(403, "Denied")):
            with self.assertRaises(HTTPException) as error:
                operations.authorized_read("token", reader)
            self.assertEqual(error.exception.status_code, 403)
            reader.assert_not_called()
        with patch.object(operations, "connect", side_effect=OperationalError("private db detail")):
            with self.assertRaises(HTTPException) as error:
                operations.authorized_read("token", reader)
            self.assertEqual(error.exception.status_code, 503)
            self.assertNotIn("private db detail", error.exception.detail)

    def test_dispatch_rejects_unknown_tools_and_model_supplied_identity(self):
        with patch.object(operations, "authorized_read") as read:
            for name, arguments in [("sql", "{}"), ("get_billing_information", '{"client_id":"other"}'),
                ("get_scheduling_information", '{"limit":true}'), ("get_scheduling_information", '{"limit":21}'),
                ("get_scheduling_information", '{"limit":1,"limit":2}'), ("get_billing_information", "[]")]:
                with self.assertRaises(ValueError):
                    tools.dispatch_tool(name, arguments, authorization="trusted")
            read.assert_not_called()
            tools.dispatch_tool("get_scheduling_information", '{"limit":3}', authorization="trusted")
            read.assert_called_once_with("trusted", operations.read_scheduling, limit=3)
            tools.dispatch_tool("get_billing_information", '{}', authorization="trusted")
            read.assert_called_with("trusted", operations.read_billing)


if __name__ == "__main__":
    unittest.main()
