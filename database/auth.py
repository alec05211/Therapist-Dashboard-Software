"""Auth0 access-token validation for the FastAPI API boundary."""

from __future__ import annotations

import os
import logging
from functools import lru_cache
from typing import Any

import jwt
from fastapi import HTTPException, status
from jwt import InvalidTokenError, PyJWKClient


# Uvicorn configures this logger explicitly, so its warnings remain visible in
# the local server terminal even when the application's module loggers have no
# handler of their own. Do not log tokens or decoded claims here.
logger = logging.getLogger("uvicorn.error")


def auth0_domain() -> str:
    value = os.getenv("AUTH0_DOMAIN", "").strip().removeprefix("https://").rstrip("/")
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth0 API validation is not configured.",
        )
    return value


def auth0_audience() -> str:
    value = os.getenv("AUTH0_AUDIENCE", "").strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth0 API audience is not configured.",
        )
    return value


@lru_cache(maxsize=1)
def jwks_client() -> PyJWKClient:
    return PyJWKClient(f"https://{auth0_domain()}/.well-known/jwks.json")


def validate_access_token(authorization: str | None) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A bearer access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A bearer access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        signing_key = jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=auth0_audience(),
            issuer=f"https://{auth0_domain()}/",
        )
    except (InvalidTokenError, jwt.PyJWKClientError) as exc:
        # Keep the browser response generic. The exception category is enough
        # to diagnose local issuer/audience/JWKS configuration without logging
        # a JWT, claims, or any user data.
        logger.warning("Auth0 access-token validation failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The access token is invalid.",
            # This is intentionally just the library exception class (for
            # example, InvalidAudienceError), never the token, claims, or
            # exception message. The Next.js development proxy can surface it
            # to the local developer without broadening the public response.
            headers={
                "WWW-Authenticate": "Bearer",
                "X-Auth-Validation-Error": type(exc).__name__,
            },
        ) from exc

    if not isinstance(claims.get("sub"), str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The access token has no subject.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims
