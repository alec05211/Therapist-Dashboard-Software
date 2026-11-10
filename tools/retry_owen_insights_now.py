"""Release Owen's context-size retry and immediately process it with local code."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=False)

from database import clinical_synthesis_worker, synthesis_refresh
from database.connection import connect


def main() -> None:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT client.id AS client_id, client.organization_id
              FROM app.clients client
              JOIN app.client_portal_accounts portal
                ON portal.client_id=client.id AND portal.status='active'
               AND portal.synthetic_case_key='heartwell-owen'
             WHERE client.display_name='Owen Park' AND client.status='active'
        """)
        rows = cursor.fetchall()
        if len(rows) != 1:
            raise RuntimeError("Expected one explicitly synthetic Owen Park client.")
        client_id = str(rows[0]["client_id"])
        organization_id = str(rows[0]["organization_id"])
        cursor.execute("""
            UPDATE app.clinical_synthesis_refresh_state
               SET status='pending', attempt_count=0, not_before=CURRENT_TIMESTAMP,
                   processing_insights_revision=NULL, worker_token=NULL,
                   lease_expires_at=NULL, updated_at=CURRENT_TIMESTAMP
             WHERE organization_id=%s AND client_id=%s AND status IN ('pending', 'failed')
               AND desired_insights_revision > published_insights_revision
               AND last_error_code IN (
                   'context_too_large', 'insights_validation_failed',
                   'provider_output_incomplete'
               )
        """, (organization_id, client_id))
        if cursor.rowcount != 1:
            raise RuntimeError("Owen's expected bounded Insights retry is not pending.")
        worker_token = str(uuid4())
        job = synthesis_refresh.claim_due_insights_refresh(
            connection,
            worker_token=worker_token,
            lease_seconds=1800,
            organization_id=organization_id,
            client_id=client_id,
        )
        if not job:
            raise RuntimeError("Could not claim Owen's released bounded Insights retry.")

    processed = clinical_synthesis_worker.process_one(
        claimed_job=job, worker_token=worker_token,
    )
    with connect() as connection:
        status = synthesis_refresh.get_refresh_status(
            connection, organization_id=organization_id, client_id=client_id,
        )
    print(json.dumps({"processed": processed, "refresh": status}, indent=2, default=str))
    if not processed or status["published_insights_revision"] < status["desired_insights_revision"]:
        raise RuntimeError("Owen's corrected Insights retry was not published.")


if __name__ == "__main__":
    main()
