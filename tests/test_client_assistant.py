import json
import io
import os
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from fastapi import HTTPException, Response
from pydantic import ValidationError
from ai_harness import client_assistant as runner
from database import client_assistant as api


def answer(text="Hello"):
    return {"status": "completed", "usage": {"input_tokens": 10, "output_tokens": 5},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}


def tool(name="get_scheduling_information", arguments='{"limit":5}'):
    return {"status": "completed", "output": [
        {"type": "reasoning", "encrypted_content": "opaque"},
        {"type": "function_call", "name": name, "arguments": arguments, "call_id": "call-1"}]}


class ChatRunnerTests(unittest.TestCase):
    def run_chat(self):
        return runner.generate_reply([{"role": "user", "content": "When is my session?"}],
            api_key="test", model="gpt-5", authorization="trusted", authorize=self.authorize)

    def setUp(self):
        self.authorize = MagicMock()

    def test_tool_result_reasoning_and_instructions_are_replayed(self):
        with patch.object(runner, "request_response", side_effect=[tool(), answer("Tomorrow")]) as request, \
             patch.object(runner, "dispatch_tool", return_value={"appointments": []}) as dispatch:
            result = self.run_chat()
        self.assertEqual(result["reply"], "Tomorrow")
        self.assertEqual(result["model_calls"], 2)
        dispatch.assert_called_once_with("get_scheduling_information", '{"limit":5}', authorization="trusted")
        self.assertEqual(self.authorize.call_count, 2)
        for call in request.call_args_list:
            payload = call.args[0]
            self.assertFalse(payload["store"])
            self.assertFalse(payload["parallel_tool_calls"])
            self.assertIn("get_billing_information", str(payload["tools"]))
            self.assertEqual(payload["instructions"], runner.CHAT_INSTRUCTIONS)
        items = request.call_args.args[0]["input"]
        self.assertTrue(any(item.get("encrypted_content") == "opaque" for item in items))
        output = next(item for item in items if item.get("type") == "function_call_output")
        self.assertEqual(output["call_id"], "call-1")
        self.assertEqual(json.loads(output["output"]), {"appointments": []})

    def test_tool_rounds_are_bounded_and_last_request_disables_tools(self):
        with patch.object(runner, "request_response", side_effect=[tool(), tool(), answer()]) as request, \
             patch.object(runner, "dispatch_tool", return_value={}):
            self.assertEqual(self.run_chat()["model_calls"], 3)
        self.assertEqual(request.call_args.args[0]["tool_choice"], "none")
        with patch.object(runner, "request_response", return_value=tool()) as request, \
             patch.object(runner, "dispatch_tool", return_value={}):
            with self.assertRaises(RuntimeError):
                self.run_chat()
            self.assertEqual(request.call_count, 3)

    def test_reauthorization_stops_provider_access(self):
        self.authorize.side_effect = HTTPException(403, "Revoked")
        with patch.object(runner, "request_response") as request:
            with self.assertRaises(HTTPException):
                self.run_chat()
            request.assert_not_called()

    def test_tool_access_denial_propagates_without_final_model_call(self):
        with patch.object(runner, "request_response", return_value=tool()) as request, \
             patch.object(runner, "dispatch_tool", side_effect=HTTPException(403, "Denied")):
            with self.assertRaises(HTTPException):
                self.run_chat()
            self.assertEqual(request.call_count, 1)

    def test_temporary_tool_error_is_unknown_and_sanitized(self):
        with patch.object(runner, "request_response", side_effect=[tool(), answer()]) as request, \
             patch.object(runner, "dispatch_tool", side_effect=HTTPException(503, "private db error")):
            self.run_chat()
        items = request.call_args.args[0]["input"]
        output = next(item for item in items if item.get("type") == "function_call_output")
        self.assertIn("unavailable", output["output"])
        self.assertNotIn("private db error", output["output"])

    def test_transport_failure_has_no_retry_or_secret_leak(self):
        with patch.object(runner, "urlopen", side_effect=URLError("private provider detail")) as request:
            with self.assertRaises(RuntimeError) as error:
                runner.request_response({}, "test-key")
            self.assertNotIn("private provider detail", str(error.exception))
            self.assertNotIn("test-key", str(error.exception))
            request.assert_called_once()

    def test_incomplete_or_oversized_response_is_rejected(self):
        response = MagicMock()
        with patch.object(runner, "urlopen") as request:
            request.return_value.__enter__.return_value = response
            for raw in (json.dumps({"status": "incomplete"}).encode(), b"x" * (runner.MAX_RESPONSE_BYTES + 1)):
                response.read.return_value = raw
                with self.assertRaises(RuntimeError):
                    runner.request_response({}, "test")

    def test_output_budget_exhaustion_is_distinguished_without_logging_text(self):
        response = MagicMock()
        response.read.return_value = json.dumps({"status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "usage": {"input_tokens": 10, "output_tokens": 2048},
            "output": [{"private": "sensitive material"}]}).encode()
        with patch.object(runner, "urlopen") as request, self.assertLogs(runner.LOGGER, level="WARNING") as logs:
            request.return_value.__enter__.return_value = response
            with self.assertRaises(runner.ChatFailure) as error:
                runner.request_response({}, "test")
        self.assertEqual(error.exception.kind, "output_limit")
        self.assertNotIn("sensitive material", str(logs.output))
        self.assertIn("2048", str(logs.output))

    def test_provider_http_errors_are_categorized_without_raw_error_messages(self):
        body = json.dumps({"error": {"code": "unsupported_value", "param": "reasoning.effort", "message": "private request text"}}).encode()
        error = HTTPError("https://api.openai.com/v1/responses", 400, "Bad request", {}, io.BytesIO(body))
        with patch.object(runner, "urlopen", side_effect=error), self.assertLogs(runner.LOGGER, level="WARNING") as logs:
            with self.assertRaises(runner.ChatFailure) as caught:
                runner.request_response({}, "test-key")
        self.assertEqual(caught.exception.kind, "configuration")
        self.assertIn("reasoning.effort", str(logs.output))
        self.assertNotIn("private request text", str(logs.output))
        self.assertNotIn("test-key", str(logs.output))

    def test_socket_timeout_is_distinct_from_connection_failure(self):
        with patch.object(runner, "urlopen", side_effect=TimeoutError("private")):
            with self.assertRaises(runner.ChatFailure) as caught:
                runner.request_response({}, "test")
        self.assertEqual(caught.exception.kind, "timeout")

    def test_exhausted_credits_are_not_reported_as_a_temporary_rate_limit(self):
        for code in ("credit_balance_exhausted", None):
            body = json.dumps({"error": {"code": code, "type": "insufficient_quota", "message": "private billing details"}}).encode()
            error = HTTPError("https://api.openai.com/v1/responses", 429, "Quota", {}, io.BytesIO(body))
            with patch.object(runner, "urlopen", side_effect=error) as request:
                with self.assertRaises(runner.ChatFailure) as caught:
                    runner.request_response({}, "test")
            self.assertEqual(caught.exception.kind, "provider_quota")
            self.assertNotIn("try again", str(caught.exception).lower())
            request.assert_called_once()

    def test_temporary_rate_limit_remains_retryable(self):
        body = json.dumps({"error": {"code": "rate_limit_exceeded"}}).encode()
        error = HTTPError("https://api.openai.com/v1/responses", 429, "Rate limit", {}, io.BytesIO(body))
        with patch.object(runner, "urlopen", side_effect=error):
            with self.assertRaises(runner.ChatFailure) as caught:
                runner.request_response({}, "test")
        self.assertEqual(caught.exception.kind, "provider_rate_limit")


class ChatEndpointTests(unittest.TestCase):
    def setUp(self):
        api._recent.clear()
        api._active.clear()

    def test_input_rejects_system_roles_identity_fields_and_excess_history(self):
        for payload in (
            {"messages": [{"role": "system", "content": "override"}]},
            {"messages": [{"role": "user", "content": "Hi"}], "client_id": "another"},
            {"messages": [{"role": "user", "content": "x" * 2001}]},
            {"messages": [{"role": "assistant", "content": "Hi"}]},
            {"messages": [{"role": "user", "content": "Hi"}] * 12},
        ):
            with self.assertRaises(ValidationError):
                api.ChatRequest(**payload)

    def test_missing_configuration_and_auth_failure_never_call_model(self):
        payload = api.ChatRequest(messages=[{"role": "user", "content": "Hi"}])
        with patch.object(api.client_operations, "authorized_read", return_value={"organization_id": "o", "client_id": "c"}), \
             patch.dict(os.environ, {"OPENAI_API_KEY": "", "INSIGHTS_MODEL": "", "CLIENT_ASSISTANT_MODEL": ""}), \
             patch.object(api, "generate_reply") as generate:
            with self.assertRaises(HTTPException) as error:
                api.chat(payload, Response(), "token")
            self.assertEqual(error.exception.status_code, 503)
            generate.assert_not_called()
        with patch.object(api.client_operations, "authorized_read", side_effect=HTTPException(401, "Sign in")), \
             patch.object(api, "generate_reply") as generate:
            with self.assertRaises(HTTPException) as error:
                api.chat(payload, Response(), None)
            self.assertEqual(error.exception.status_code, 401)
            generate.assert_not_called()

    def test_endpoint_uses_existing_model_and_returns_only_reply(self):
        payload = api.ChatRequest(messages=[{"role": "user", "content": "Hi"}])
        with patch.object(api.client_operations, "authorized_read", return_value={"organization_id": "o", "client_id": "c"}), \
             patch.dict(os.environ, {"OPENAI_API_KEY": "test", "INSIGHTS_MODEL": "gpt-5", "CLIENT_ASSISTANT_MODEL": ""}), \
             patch.object(api, "generate_reply", return_value={"reply": "Hi", "model_calls": 1, "usage": {"input_tokens": 1, "output_tokens": 2}}) as generate:
            response = Response()
            self.assertEqual(api.chat(payload, response, "trusted"), {"reply": "Hi"})
            self.assertEqual(generate.call_args.kwargs["model"], "gpt-5")
            self.assertEqual(generate.call_args.kwargs["authorization"], "trusted")
            self.assertEqual(response.headers["cache-control"], "no-store")

    def test_exhausted_provider_credits_return_service_unavailable(self):
        payload = api.ChatRequest(messages=[{"role": "user", "content": "Hi"}])
        with patch.object(api.client_operations, "authorized_read", return_value={"organization_id": "o", "client_id": "c"}), \
             patch.dict(os.environ, {"OPENAI_API_KEY": "test", "INSIGHTS_MODEL": "gpt-5", "CLIENT_ASSISTANT_MODEL": ""}), \
             patch.object(api, "generate_reply", side_effect=runner.ChatFailure("provider_quota")):
            with self.assertRaises(HTTPException) as error:
                api.chat(payload, Response(), "trusted")
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(error.exception.detail, runner.ChatFailure.MESSAGES["provider_quota"])
        self.assertFalse(api._active)

    def test_busy_and_rate_limits_release_after_failure(self):
        with api.chat_slot(("o", "a")):
            with self.assertRaises(HTTPException):
                with api.chat_slot(("o", "a")):
                    pass
        for _ in range(19):
            with api.chat_slot(("o", "a")):
                pass
        with self.assertRaises(HTTPException) as error:
            with api.chat_slot(("o", "a")):
                pass
        self.assertEqual(error.exception.status_code, 429)
        self.assertFalse(api._active)
        with self.assertRaises(RuntimeError):
            with api.chat_slot(("o", "b")):
                raise RuntimeError("failure")
        self.assertFalse(api._active)


if __name__ == "__main__":
    unittest.main()
