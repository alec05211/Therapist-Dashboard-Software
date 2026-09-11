"""Apply ordered PostgreSQL migrations and record their checksums.

Run this only from a network location explicitly allowed to reach the private
RDS instance. The migration connection is an administrative connection; the
application runtime should receive narrower database permissions before any
production use.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import psycopg


MIGRATIONS_DIRECTORY = Path(__file__).with_name("migrations")


def database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is required to run migrations.")
    if "sslmode=" not in value:
        raise RuntimeError(
            "DATABASE_URL must explicitly require TLS, for example sslmode=verify-full."
        )
    return value


def migration_files() -> list[Path]:
    files = sorted(MIGRATIONS_DIRECTORY.glob("[0-9][0-9][0-9]_*.sql"))
    if not files:
        raise RuntimeError(f"No migrations found in {MIGRATIONS_DIRECTORY}.")
    return files


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    try:
        connection_url = database_url()
        with psycopg.connect(connection_url, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("CREATE SCHEMA IF NOT EXISTS app")
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app.schema_migrations (
                      name text PRIMARY KEY,
                      checksum text NOT NULL,
                      applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                for path in migration_files():
                    name = path.name
                    digest = checksum(path)
                    cursor.execute(
                        "SELECT checksum FROM app.schema_migrations WHERE name = %s",
                        (name,),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        if existing[0] != digest:
                            raise RuntimeError(
                                f"Migration {name} was changed after it was applied. "
                                "Create a new migration instead."
                            )
                        print(f"Already applied: {name}")
                        continue

                    print(f"Applying: {name}")
                    cursor.execute(path.read_text(encoding="utf-8"))
                    cursor.execute(
                        "INSERT INTO app.schema_migrations (name, checksum) VALUES (%s, %s)",
                        (name, digest),
                    )
    except (OSError, psycopg.Error, RuntimeError) as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1

    print("Migrations complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
