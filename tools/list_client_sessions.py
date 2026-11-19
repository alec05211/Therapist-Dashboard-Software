"""List exact stored sessions for one explicitly named client without exposing credentials."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database.connection import connect


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-name", required=True)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT session.id,
                      session.appointment_id,
                      session.started_at,
                      session.ended_at,
                      job.status,
                      count(artifact.id) AS artifact_count,
                      count(artifact.id) FILTER (
                          WHERE artifact.artifact_type='audio_recording'
                            AND artifact.lifecycle_state <> 'deleted'
                      ) AS recording_count
                 FROM app.sessions session
                 JOIN app.clients client ON client.id=session.client_id
                 LEFT JOIN app.session_storage_jobs job ON job.session_id=session.id
                 LEFT JOIN app.clinical_artifacts artifact ON artifact.session_id=session.id
                WHERE lower(client.display_name)=lower(%s)
                GROUP BY session.id, session.appointment_id, session.started_at,
                         session.ended_at, job.status
                ORDER BY session.started_at, session.id""",
            (args.client_name,),
        )
        rows = cursor.fetchall()

    print(f"Stored sessions for {args.client_name}: {len(rows)}")
    for row in rows:
        print(
            f"{row['id']} | appointment={row['appointment_id']} | "
            f"started={row['started_at']} | status={row['status']} | "
            f"recordings={row['recording_count']} | artifacts={row['artifact_count']}"
        )


if __name__ == "__main__":
    main()
