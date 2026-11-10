"""Process only Owen Park's due synthetic Insights revision."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=False)

from database import clinical_synthesis_worker, synthesis_refresh
from database.connection import connect


def main() -> None:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT client.id AS client_id, client.organization_id
                 FROM app.clients client
                 JOIN app.client_portal_accounts portal
                   ON portal.client_id=client.id AND portal.status='active'
                  AND portal.synthetic_case_key='heartwell-owen'
                WHERE client.display_name='Owen Park' AND client.status='active'"""
        )
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise RuntimeError("Expected one explicitly synthetic Owen Park client.")
    organization_id = str(rows[0]["organization_id"])
    client_id = str(rows[0]["client_id"])
    processed = clinical_synthesis_worker.process_one(
        organization_id=organization_id, client_id=client_id,
    )
    with connect() as connection:
        status = synthesis_refresh.get_refresh_status(
            connection, organization_id=organization_id, client_id=client_id,
        )
    print(json.dumps({"processed": processed, "refresh": status}, indent=2, default=str))
    if status["published_insights_revision"] < status["desired_insights_revision"]:
        raise RuntimeError("Owen's latest Insights revision was not published.")


if __name__ == "__main__":
    main()
