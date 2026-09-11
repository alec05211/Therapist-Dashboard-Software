"""Minimal PostgreSQL connection helpers for the FastAPI application."""

from __future__ import annotations

import os

import psycopg
from psycopg.rows import dict_row


def connect() -> psycopg.Connection:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    if "sslmode=" not in database_url:
        raise RuntimeError("DATABASE_URL must explicitly require TLS.")
    return psycopg.connect(database_url, row_factory=dict_row)
