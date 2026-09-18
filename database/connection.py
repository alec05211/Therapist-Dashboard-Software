"""Minimal PostgreSQL connection helpers for the FastAPI application."""

from __future__ import annotations

import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlretrieve

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import psycopg
from psycopg.rows import dict_row


RDS_GLOBAL_CA_URL = "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem"


def connect() -> psycopg.Connection:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        database_url = (
            database_url_from_runtime_credentials()
            if os.getenv("DATABASE_USERNAME")
            else database_url_from_local_aws_secret()
        )
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


@lru_cache(maxsize=1)
def rds_ca_bundle_path() -> str:
    """Return a configured CA bundle or cache AWS's public RDS bundle locally."""
    configured_path = os.getenv("RDS_CA_BUNDLE")
    if configured_path:
        if not Path(configured_path).is_file():
            raise RuntimeError("RDS_CA_BUNDLE does not point to a readable certificate bundle.")
        return configured_path

    cache_path = Path(tempfile.gettempdir()) / "therapist-dashboard-rds-global-bundle.pem"
    if not cache_path.is_file():
        try:
            urlretrieve(RDS_GLOBAL_CA_URL, cache_path)
        except OSError as exc:
            raise RuntimeError("Could not retrieve the public AWS RDS certificate bundle.") from exc
    return str(cache_path)


def database_url_from_local_aws_secret() -> str:
    """Build a TLS URL from an RDS-managed secret for the local synthetic demo.

    The secret ARN, host, and database name are identifiers rather than
    credentials. The password remains in memory for the duration of a single
    connection attempt and is never written to an environment file.
    """
    secret_arn = os.getenv("DATABASE_SECRET_ARN")
    if not secret_arn:
        raise RuntimeError(
            "DATABASE_URL is not configured and no runtime credentials or DATABASE_SECRET_ARN are available."
        )
    try:
        response = boto3.client(
            "secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-1")
        ).get_secret_value(SecretId=secret_arn)
        secret = json.loads(response["SecretString"])
    except (BotoCoreError, ClientError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Could not retrieve the configured RDS managed secret.") from exc

    username = secret.get("username")
    password = secret.get("password")
    host = os.getenv("DATABASE_HOST") or secret.get("host")
    database_name = os.getenv("DATABASE_NAME") or secret.get("dbname")
    if not all(isinstance(value, str) and value for value in (username, password, host, database_name)):
        raise RuntimeError("The configured RDS managed secret is missing required connection fields.")

    certificate = rds_ca_bundle_path()
    return (
        f"postgresql://{quote(username, safe='')}:{quote(password, safe='')}@{host}:5432/{database_name}"
        f"?sslmode=verify-full&sslrootcert={quote(certificate, safe='/')}"
    )
