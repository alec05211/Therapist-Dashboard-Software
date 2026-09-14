"""Minimal PostgreSQL connection helpers for the FastAPI application."""

from __future__ import annotations

import os
from urllib.parse import quote

import psycopg
from psycopg.rows import dict_row


def connect() -> psycopg.Connection:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        database_url = database_url_from_runtime_credentials()
    if "sslmode=" not in database_url:
        raise RuntimeError("DATABASE_URL must explicitly require TLS.")
    return psycopg.connect(database_url, row_factory=dict_row)


def database_url_from_runtime_credentials() -> str:
    """Build a TLS connection URL from ECS-injected RDS secret fields."""
    required = ("DATABASE_USERNAME", "DATABASE_PASSWORD", "DATABASE_HOST", "DATABASE_NAME")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "DATABASE_URL is not configured and runtime database credentials are missing: "
            + ", ".join(missing)
        )

    username = quote(os.environ["DATABASE_USERNAME"], safe="")
    password = quote(os.environ["DATABASE_PASSWORD"], safe="")
    host = os.environ["DATABASE_HOST"]
    database_name = os.environ["DATABASE_NAME"]
    certificate = os.getenv("RDS_CA_BUNDLE", "/app/rds-ca-bundle.pem")
    return (
        f"postgresql://{username}:{password}@{host}:5432/{database_name}"
        f"?sslmode=verify-full&sslrootcert={quote(certificate, safe='/')}"
    )
