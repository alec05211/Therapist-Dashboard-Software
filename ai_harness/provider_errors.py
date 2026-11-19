"""Sanitized model-provider failures for operational diagnostics."""
from __future__ import annotations

import json
import re
from urllib.error import HTTPError


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_RESET_VALUE = re.compile(r"^[0-9]+(?:ms|s|m|h)(?:[0-9]+(?:ms|s|m|h))*$")
_INTEGER_HEADERS = {
    "rate_limit_limit_requests": "x-ratelimit-limit-requests",
    "rate_limit_remaining_requests": "x-ratelimit-remaining-requests",
    "rate_limit_limit_tokens": "x-ratelimit-limit-tokens",
    "rate_limit_remaining_tokens": "x-ratelimit-remaining-tokens",
    "rate_limit_limit_project_tokens": "x-ratelimit-limit-project-tokens",
    "rate_limit_remaining_project_tokens": "x-ratelimit-remaining-project-tokens",
}
_RESET_HEADERS = {
    "rate_limit_reset_requests": "x-ratelimit-reset-requests",
    "rate_limit_reset_tokens": "x-ratelimit-reset-tokens",
    "rate_limit_reset_project_tokens": "x-ratelimit-reset-project-tokens",
}


def _identifier(value):
    return value if isinstance(value, str) and _IDENTIFIER.fullmatch(value) else None


class ProviderRequestError(RuntimeError):
    """A provider rejection containing only allowlisted operational metadata."""

    def __init__(self, *, provider: str, status_code: int, error_code: str | None = None,
                 error_type: str | None = None, request_id: str | None = None,
                 retry_after_seconds: int | None = None, rate_limits: dict | None = None):
        self.provider = provider
        self.status_code = status_code
        self.error_code = _identifier(error_code)
        self.error_type = _identifier(error_type)
        self.request_id = _identifier(request_id)
        self.retry_after_seconds = retry_after_seconds
        self.rate_limits = dict(rate_limits or {})
        safe_code = self.error_code or self.error_type or f"http_{status_code}"
        super().__init__(f"{provider} request failed ({status_code}, {safe_code})")

    def diagnostic_details(self) -> dict:
        details = {
            "provider": self.provider,
            "provider_status_code": self.status_code,
        }
        if self.error_code:
            details["provider_error_code"] = self.error_code
        if self.error_type:
            details["provider_error_type"] = self.error_type
        if self.request_id:
            details["provider_request_id"] = self.request_id
        if self.retry_after_seconds is not None:
            details["retry_after_seconds"] = self.retry_after_seconds
        details.update(self.rate_limits)
        return details


def provider_error_from_http_error(exc: HTTPError, *, provider: str) -> ProviderRequestError:
    """Consume a provider error without retaining its possibly sensitive body."""
    raw = exc.read().decode("utf-8", errors="replace")
    error = {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("error"), dict):
            error = parsed["error"]
    except (json.JSONDecodeError, UnicodeError):
        pass

    headers = exc.headers
    rate_limits = {}
    for field, header in _INTEGER_HEADERS.items():
        value = headers.get(header) if headers else None
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= number <= 10**12:
            rate_limits[field] = number
    for field, header in _RESET_HEADERS.items():
        value = headers.get(header) if headers else None
        if isinstance(value, str) and _RESET_VALUE.fullmatch(value):
            rate_limits[field] = value

    retry_after = headers.get("Retry-After") if headers else None
    try:
        retry_after_seconds = max(0, min(86_400, int(float(retry_after))))
    except (TypeError, ValueError):
        retry_after_seconds = None

    return ProviderRequestError(
        provider=provider,
        status_code=int(exc.code),
        error_code=error.get("code"),
        error_type=error.get("type"),
        request_id=(headers.get("x-request-id") if headers else None),
        retry_after_seconds=retry_after_seconds,
        rate_limits=rate_limits,
    )
