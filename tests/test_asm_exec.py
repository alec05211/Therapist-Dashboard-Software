import importlib.machinery
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


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
