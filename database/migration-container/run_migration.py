"""Construct a verified in-VPC RDS connection for the one-off ECS task."""

from __future__ import annotations

import os
from urllib.parse import quote

from migrate import main


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


if __name__ == "__main__":
    username = quote(required("DATABASE_USERNAME"), safe="")
    password = quote(required("DATABASE_PASSWORD"), safe="")
    host = required("DATABASE_HOST")
    name = required("DATABASE_NAME")
    os.environ["DATABASE_URL"] = (
        f"postgresql://{username}:{password}@{host}:5432/{name}"
        "?sslmode=verify-full&sslrootcert=/app/rds-ca-bundle.pem"
    )
    raise SystemExit(main())
