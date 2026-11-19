import io
import unittest
from email.message import Message
from urllib.error import HTTPError

from ai_harness.provider_errors import provider_error_from_http_error


class ProviderErrorTests(unittest.TestCase):
    def test_http_error_is_reduced_to_safe_operational_fields(self):
        headers = Message()
        headers['x-request-id'] = 'req_abc123'
        headers['Retry-After'] = '56'
        headers['x-ratelimit-limit-tokens'] = '150000'
        headers['x-ratelimit-remaining-tokens'] = '0'
        headers['x-ratelimit-reset-tokens'] = '6m0s'
        body = b'{"error":{"code":"slow_down","type":"rate_limit_error","message":"private provider detail"}}'
        source = HTTPError(
            'https://api.openai.com/v1/responses', 429, 'Too Many Requests',
            headers, io.BytesIO(body),
        )

        error = provider_error_from_http_error(source, provider='openai')

        self.assertEqual(error.diagnostic_details(), {
            'provider': 'openai', 'provider_status_code': 429,
            'provider_error_code': 'slow_down', 'provider_error_type': 'rate_limit_error',
            'provider_request_id': 'req_abc123', 'retry_after_seconds': 56,
            'rate_limit_limit_tokens': 150000, 'rate_limit_remaining_tokens': 0,
            'rate_limit_reset_tokens': '6m0s',
        })
        self.assertNotIn('private provider detail', str(error))

    def test_invalid_provider_values_and_body_are_not_retained(self):
        headers = Message()
        headers['x-request-id'] = 'unsafe request id with spaces'
        headers['x-ratelimit-reset-tokens'] = 'private value'
        source = HTTPError(
            'https://api.openai.com/v1/responses', 500, 'Error', headers,
            io.BytesIO(b'not-json clinical or provider text'),
        )

        error = provider_error_from_http_error(source, provider='openai')

        self.assertEqual(error.diagnostic_details(), {
            'provider': 'openai', 'provider_status_code': 500,
        })
        self.assertNotIn('clinical', str(error))


if __name__ == '__main__':
    unittest.main()
