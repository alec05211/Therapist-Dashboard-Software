"""Queue one audited Insights reprocess request for an explicitly named client."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database.connection import connect
from database import synthesis_refresh


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-name", required=True)
    parser.add_argument("--reason", default="administrative_recovery")
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()

    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT DISTINCT client.id, access.organization_id
                 FROM app.clients client
                 JOIN app.client_therapist_access access
                   ON access.client_id=client.id
                  AND access.organization_id=client.organization_id
                WHERE lower(client.display_name)=lower(%s)
                  AND client.status <> 'archived' AND client.archived_at IS NULL
                  AND access.revoked_at IS NULL
                  AND access.effective_from <= CURRENT_TIMESTAMP
                  AND (access.effective_until IS NULL OR access.effective_until > CURRENT_TIMESTAMP)
                ORDER BY client.id""",
            (args.client_name,),
        )
        clients = cursor.fetchall()
        if len(clients) != 1:
            raise RuntimeError(
                f"Expected exactly one active client named {args.client_name}; found {len(clients)}."
            )
        client_id = str(clients[0]["id"])
        organization_id = str(clients[0]["organization_id"])

        cursor.execute(
            """SELECT status, desired_insights_revision, published_insights_revision,
                      processing_insights_revision, attempt_count, last_error_code
                 FROM app.clinical_synthesis_refresh_state
                WHERE organization_id=%s AND client_id=%s
                FOR UPDATE""",
            (organization_id, client_id),
        )
        prior = cursor.fetchone()
        if not prior:
            raise RuntimeError("The client has no Insights refresh state to recover.")
        if args.status_only:
            print(
                f"Insights status for {args.client_name}: {prior['status']}; "
                f"desired revision {prior['desired_insights_revision']}; "
                f"published revision {prior['published_insights_revision']}; "
                f"processing revision {prior['processing_insights_revision']}; "
                f"attempt {prior['attempt_count']}; "
                f"error {prior['last_error_code'] or 'none'}."
            )
            return
        if prior["status"] == "running":
            raise RuntimeError("Insights is already running; no recovery request was queued.")

        revision = synthesis_refresh.enqueue_insights_refresh(
            connection,
            organization_id=organization_id,
            client_id=client_id,
            event_type="reprocess_requested",
            target_type="client",
            target_id=client_id,
            metadata={"reason": args.reason},
            debounce_seconds=0,
        )
        cursor.execute(
            """UPDATE app.clinical_synthesis_refresh_state
                  SET status='pending', attempt_count=0, not_before=CURRENT_TIMESTAMP,
                      processing_insights_revision=NULL, worker_token=NULL,
                      lease_expires_at=NULL, last_error_code=NULL,
                      updated_at=CURRENT_TIMESTAMP
                WHERE organization_id=%s AND client_id=%s
                  AND desired_insights_revision=%s
                  AND status='pending'""",
            (organization_id, client_id, revision),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("The Insights recovery request could not be scheduled atomically.")
        connection.commit()

    print(
        f"Queued Insights revision {revision} for {args.client_name}; "
        f"previous status was {prior['status']}."
    )


if __name__ == "__main__":
    main()
