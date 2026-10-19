import importlib.machinery
import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch


def load_asm_exec():
    path = Path(__file__).parents[1] / "deploy" / "hosted-demo" / "asm-exec"
    loader = importlib.machinery.SourceFileLoader("hosted_demo_asm_exec", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class AsmExecTests(unittest.TestCase):
    def setUp(self):
        self.module = load_asm_exec()
        self.module._secret_cache.clear()

    def test_reads_the_local_provider_token_from_its_protected_file(self):
        self.module.SMA_TOKEN_FILE = "/var/run/awssmatoken"
        with patch.dict(os.environ, {}, clear=True), patch(
            "builtins.open", mock_open(read_data="local-token\n")
        ) as token_file:
            token = self.module._get_ssrf_token()

        self.assertEqual(token, "local-token")
        token_file.assert_called_once_with("/var/run/awssmatoken", encoding="utf-8")

    def test_reads_a_file_uri_token_without_exposing_it(self):
        with patch.dict(
            os.environ, {"AWS_TOKEN": "file:///run/provider-token"}, clear=True
        ), patch("builtins.open", mock_open(read_data="file-token\n")) as token_file:
            token = self.module._get_ssrf_token()

        self.assertEqual(token, "file-token")
        token_file.assert_called_once_with("/run/provider-token", encoding="utf-8")

    def test_provider_health_check_sends_the_ssrf_token(self):
        self.module._sma_available = None
        response = MagicMock()
        with patch.object(
            self.module, "_get_ssrf_token", return_value="health-token"
        ), patch.object(self.module.urllib.request, "urlopen", return_value=response) as open_url:
            self.assertTrue(self.module._check_sma())

        request = open_url.call_args.args[0]
        self.assertEqual(
            request.get_header("X-aws-parameters-secrets-token"), "health-token"
        )

    def test_required_provider_does_not_fall_back_to_remote_mcp(self):
        self.module.REQUIRE_SMA = True
        with patch.object(self.module, "_check_sma", return_value=False), patch.object(
            self.module, "_resolve_via_mcp"
        ) as resolve:
            with self.assertRaises(SystemExit):
                self.module.resolve_one("runtime")

        resolve.assert_not_called()

    def test_reuses_one_secret_string_for_multiple_json_keys(self):
        secret = json.dumps({"AUTH0_DOMAIN": "example.auth0.com", "AUTH0_AUDIENCE": "example-api"})
        prefix = "arn:aws:secretsmanager:us-east-1:123456789012:secret:runtime-AbCdEf"

        with patch.object(self.module, "_check_sma", return_value=False), patch.object(
            self.module, "_resolve_via_mcp", return_value=secret
        ) as resolve:
            domain = self.module.resolve_one(f"{prefix}:SecretString:AUTH0_DOMAIN")
            audience = self.module.resolve_one(f"{prefix}:SecretString:AUTH0_AUDIENCE")

        self.assertEqual(domain, "example.auth0.com")
        self.assertEqual(audience, "example-api")
        resolve.assert_called_once_with(prefix, "AWSCURRENT", "us-east-1")

    def test_retries_a_transient_timeout(self):
        self.module.MCP_ATTEMPTS = 2
        with patch.object(
            self.module,
            "_resolve_via_mcp_once",
            side_effect=[TimeoutError("read timed out"), "resolved-secret"],
        ) as resolve, patch.object(self.module.time, "sleep") as sleep:
            value = self.module._resolve_via_mcp("runtime", "AWSCURRENT", "us-east-1")

        self.assertEqual(value, "resolved-secret")
        self.assertEqual(resolve.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_retries_a_transient_internal_service_error(self):
        self.module.MCP_ATTEMPTS = 2
        service_error = self.module.TransientMCPError(
            "run_script reported an error: An internal error occurred. Please try again."
        )
        with patch.object(
            self.module,
            "_resolve_via_mcp_once",
            side_effect=[service_error, "resolved-secret"],
        ) as resolve, patch.object(self.module.time, "sleep") as sleep:
            value = self.module._resolve_via_mcp("runtime", "AWSCURRENT", "us-east-1")

        self.assertEqual(value, "resolved-secret")
        self.assertEqual(resolve.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_classifies_access_denied_as_permanent(self):
        with self.assertRaises(RuntimeError) as raised:
            self.module._raise_mcp_error("run_script reported an error", "AccessDeniedException")

        self.assertNotIsInstance(raised.exception, self.module.TransientMCPError)

    def test_classifies_internal_error_as_transient(self):
        with self.assertRaises(self.module.TransientMCPError):
            self.module._raise_mcp_error(
                "run_script reported an error",
                "An internal error occurred. Please try again.",
            )

    def test_does_not_retry_a_permission_failure(self):
        self.module.MCP_ATTEMPTS = 2
        with patch.object(
            self.module,
            "_resolve_via_mcp_once",
            side_effect=RuntimeError("access denied"),
        ) as resolve, patch.object(self.module.time, "sleep") as sleep:
            value = self.module._resolve_via_mcp("runtime", "AWSCURRENT", "us-east-1")

        self.assertIsNone(value)
        resolve.assert_called_once()
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
