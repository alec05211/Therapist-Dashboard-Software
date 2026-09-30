import unittest
from unittest.mock import MagicMock, patch

from database import auth


class AccessTokenValidationTests(unittest.TestCase):
    @patch.dict("os.environ", {"AUTH0_DOMAIN": "example.auth0.com", "AUTH0_AUDIENCE": "test-audience"})
    @patch.object(auth.jwt, "decode", return_value={"sub": "auth0|user"})
    @patch.object(auth, "jwks_client")
    def test_allows_small_clock_skew_without_weakening_claim_checks(self, client, decode):
        client.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")

        claims = auth.validate_access_token("Bearer token")

        self.assertEqual(claims["sub"], "auth0|user")
        decode.assert_called_once_with(
            "token",
            "public-key",
            algorithms=["RS256"],
            audience="test-audience",
            issuer="https://example.auth0.com/",
            leeway=5,
        )


if __name__ == "__main__":
    unittest.main()
