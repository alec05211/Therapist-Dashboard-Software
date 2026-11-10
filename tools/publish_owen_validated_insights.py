"""Generate once, retain a validated Owen draft, then publish that exact draft."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=False)

from ai_harness.longitudinal_insights import generate_openai_longitudinal_insights
from database import clinical_synthesis_worker, synthesis_refresh
from database.clinical_context import build_clinical_context
from database.connection import connect


def main() -> None:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT client.id AS client_id, client.organization_id,
                   actor.id AS actor_user_id
              FROM app.clients client
              JOIN app.client_portal_accounts portal
                ON portal.client_id=client.id AND portal.status='active'
               AND portal.synthetic_case_key='heartwell-owen'
              JOIN app.client_therapist_access access
                ON access.client_id=client.id AND access.organization_id=client.organization_id
               AND access.revoked_at IS NULL AND access.can_write_clinical
              JOIN app.organization_practitioners practitioner
                ON practitioner.id=access.practitioner_id
              JOIN app.organization_memberships membership
                ON membership.id=practitioner.membership_id AND membership.status='active'
              JOIN app.application_users actor
                ON actor.id=membership.user_id AND actor.status='active'
             WHERE client.display_name='Owen Park' AND client.status='active'
               AND practitioner.professional_name='Jeremy Heartwell'
        """)
        rows = cursor.fetchall()
        if len(rows) != 1:
            raise RuntimeError("Expected one explicitly synthetic Owen Park client.")
        client_id = str(rows[0]["client_id"])
        organization_id = str(rows[0]["organization_id"])
        actor_user_id = str(rows[0]["actor_user_id"])
        context = build_clinical_context(
            connection, organization_id=organization_id, client_id=client_id,
        )

    evidence = context["source_evidence"]
    aliases = {f"E{index:03d}": source["evidence_id"] for index, source in enumerate(evidence, 1)}
    source_to_alias = {value: key for key, value in aliases.items()}

    generated = metadata = None
    attempts = []
    for attempt in range(1, 4):
        try:
            generated, metadata = generate_openai_longitudinal_insights(
                evidence=evidence,
                clinical_context=context,
                api_key=os.environ["OPENAI_API_KEY"],
                model=os.environ["INSIGHTS_MODEL"],
            )
            attempts.append({"attempt": attempt, "valid": True})
            break
        except RuntimeError as exc:
            attempts.append({
                "attempt": attempt,
                "valid": False,
                "failure": (
                    "validation" if hasattr(exc, "violations")
                    else "provider"
                ),
            })
    if generated is None or metadata is None:
        print(json.dumps({"attempts": attempts}, indent=2))
        raise RuntimeError("No Owen Insights draft passed validation in three bounded attempts.")

    for item in generated["items"]:
        for claim in item.get("analysis_claims") or []:
            claim["evidence_ids"] = [source_to_alias[value] for value in claim["evidence_ids"]]
        for statement in item.get("context_statements") or []:
            for claim in statement.get("claims") or []:
                claim["evidence_ids"] = [source_to_alias[value] for value in claim["evidence_ids"]]
        for link in item.get("evidence_roles") or []:
            link["evidence_id"] = source_to_alias[link["evidence_id"]]

    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT desired_insights_revision, published_insights_revision
              FROM app.clinical_synthesis_refresh_state
             WHERE organization_id=%s AND client_id=%s
             FOR UPDATE
        """, (organization_id, client_id))
        state = cursor.fetchone()
        if state and int(state["desired_insights_revision"]) == int(state["published_insights_revision"]):
            synthesis_refresh.enqueue_insights_refresh(
                connection,
                organization_id=organization_id,
                client_id=client_id,
                event_type="reprocess_requested",
                actor_user_id=actor_user_id,
                target_type="client",
                target_id=client_id,
                debounce_seconds=0,
            )
        cursor.execute("""
            UPDATE app.clinical_synthesis_refresh_state
               SET status='pending', attempt_count=0, not_before=CURRENT_TIMESTAMP,
                   processing_insights_revision=NULL, worker_token=NULL,
                   lease_expires_at=NULL, updated_at=CURRENT_TIMESTAMP
             WHERE organization_id=%s AND client_id=%s AND status IN ('pending', 'failed')
               AND desired_insights_revision > published_insights_revision
        """, (organization_id, client_id))
        if cursor.rowcount != 1:
            raise RuntimeError("Owen's expected Insights revision is not pending.")
        worker_token = str(uuid4())
        job = synthesis_refresh.claim_due_insights_refresh(
            connection, worker_token=worker_token, lease_seconds=1800,
            organization_id=organization_id, client_id=client_id,
        )
        if not job:
            raise RuntimeError("Could not atomically claim Owen's validated Insights revision.")

    processed = clinical_synthesis_worker.process_one(
        claimed_job=job,
        worker_token=worker_token,
        insight_generator=lambda **_: (generated, metadata),
    )
    with connect() as connection:
        status = synthesis_refresh.get_refresh_status(
            connection, organization_id=organization_id, client_id=client_id,
        )
    print(json.dumps({
        "attempts": attempts,
        "processed": processed,
        "refresh": status,
    }, indent=2, default=str))
    if status["published_insights_revision"] < status["desired_insights_revision"]:
        raise RuntimeError("The validated Owen Insights draft was not published.")


if __name__ == "__main__":
    main()
