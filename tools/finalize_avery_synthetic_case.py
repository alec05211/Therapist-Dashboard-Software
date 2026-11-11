"""Finalize Avery's first three synthetic sessions and accept their evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=False)

from database import client_journey, journey_proposal_jobs, synthesis_refresh
from database.connection import connect
from database.longitudinal_records import LongitudinalRecordRepository


def configure_database(args: argparse.Namespace) -> None:
    ca_path = str(Path(args.sslrootcert).resolve()).replace("\\", "/")
    os.environ["DATABASE_URL"] = (
        f"postgresql://{quote(args.username, safe='')}:{quote(args.password, safe='')}"
        f"@{args.host}:5432/{quote(args.database, safe='')}"
        f"?sslmode=verify-full&sslrootcert={quote(ca_path, safe='/:')}"
    )


def context() -> dict[str, str]:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT client.id AS client_id, client.organization_id,
                      actor.id AS actor_user_id
                 FROM app.clients client
                 JOIN app.client_portal_accounts portal
                   ON portal.client_id=client.id AND portal.status='active'
                  AND portal.synthetic_case_key='heartwell-avery'
                 JOIN app.client_therapist_access access
                   ON access.client_id=client.id AND access.organization_id=client.organization_id
                  AND access.revoked_at IS NULL AND access.can_write_clinical
                 JOIN app.organization_practitioners practitioner
                   ON practitioner.id=access.practitioner_id
                 JOIN app.organization_memberships membership
                   ON membership.id=practitioner.membership_id AND membership.status='active'
                 JOIN app.application_users actor
                   ON actor.id=membership.user_id AND actor.status='active'
                WHERE client.display_name='Avery Chen' AND client.status='active'
                  AND practitioner.professional_name='Jeremy Heartwell'"""
        )
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise RuntimeError("Expected one explicitly synthetic Avery and Jeremy care relationship.")
    return {key: str(value) for key, value in rows[0].items()}


def note_content(sections: list[dict[str, object]]) -> dict[str, object]:
    nodes: list[dict[str, object]] = []
    plain: list[str] = []
    for section in sections:
        name = str(section.get("name") or "Clinical note")
        items = [str(item) for item in section.get("items") or [] if str(item).strip()]
        plain.extend([name, *items])
        nodes.append({"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": name}]})
        nodes.append({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": item}]}]}
                for item in items
            ],
        })
    return {
        "schema_version": 1,
        "editor": "tiptap",
        "document": {"type": "doc", "content": nodes},
        "plain_text": "\n".join(plain),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--sslrootcert", required=True)
    args = parser.parse_args()
    configure_database(args)
    scope = context()

    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT session.id, session.status AS session_status,
                      transcript.id AS transcript_version_id,
                      transcript.status AS transcript_status,
                      synthesis.id AS synthesis_id, synthesis.content,
                      COALESCE(job.storage->>'label', 'Completed session') AS label
                 FROM app.sessions session
                 JOIN app.session_storage_jobs job
                   ON job.session_id=session.id AND job.status='COMPLETED'
                 JOIN LATERAL (
                   SELECT id, status FROM app.transcript_versions
                    WHERE session_id=session.id ORDER BY version_number DESC LIMIT 1
                 ) transcript ON true
                 JOIN LATERAL (
                   SELECT id, content FROM app.synthesis_versions
                    WHERE session_id=session.id AND status <> 'superseded'
                    ORDER BY version_number DESC LIMIT 1
                 ) synthesis ON true
                WHERE session.organization_id=%s AND session.client_id=%s
                ORDER BY session.started_at""",
            (scope["organization_id"], scope["client_id"]),
        )
        sessions = cursor.fetchall()
    if len(sessions) != 3:
        raise RuntimeError(f"Expected exactly three completed Avery sessions; found {len(sessions)}.")

    finalized_transcripts = []
    for session in sessions:
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE app.transcript_versions
                      SET status='finalized', finalized_by_user_id=%s,
                          finalized_at=COALESCE(finalized_at, CURRENT_TIMESTAMP)
                    WHERE id=%s AND organization_id=%s AND client_id=%s
                      AND status <> 'finalized'
                    RETURNING id""",
                (scope["actor_user_id"], session["transcript_version_id"],
                 scope["organization_id"], scope["client_id"]),
            )
            changed = cursor.fetchone() is not None
            cursor.execute(
                """UPDATE app.sessions SET status='finalized', updated_at=CURRENT_TIMESTAMP
                    WHERE id=%s AND organization_id=%s AND client_id=%s
                      AND status IN ('review','finalized')""",
                (session["id"], scope["organization_id"], scope["client_id"]),
            )
            if changed:
                synthesis_refresh.enqueue_insights_refresh(
                    connection,
                    organization_id=scope["organization_id"],
                    client_id=scope["client_id"],
                    event_type="transcript_finalized",
                    actor_user_id=scope["actor_user_id"],
                    target_type="transcript_version",
                    target_id=str(session["transcript_version_id"]),
                )
        finalized_transcripts.append({
            "session_id": str(session["id"]),
            "transcript_version_id": str(session["transcript_version_id"]),
            "changed": changed,
        })

    proposal_jobs = []
    for session in sessions:
        processed = journey_proposal_jobs.process_one(session_id=str(session["id"]))
        proposal_jobs.append({"session_id": str(session["id"]), "processed": processed})

    session_ids = [session["id"] for session in sessions]
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT session_id, status, attempt_count, last_error_code
                 FROM app.journey_proposal_analysis_jobs
                WHERE organization_id=%s AND client_id=%s AND session_id=ANY(%s)
                ORDER BY created_at""",
            (scope["organization_id"], scope["client_id"], session_ids),
        )
        proposal_job_statuses = cursor.fetchall()
    incomplete = [row for row in proposal_job_statuses if row["status"] != "completed"]
    if len(proposal_job_statuses) != 3 or incomplete:
        raise RuntimeError(
            "All three transcript evidence analyses must complete before acceptance: "
            + json.dumps(proposal_job_statuses, default=str)
        )

    finalized_notes = []
    for session in sessions:
        session_id = str(session["id"])
        with connect() as connection:
            repository = LongitudinalRecordRepository(connection)
            latest = repository.get_latest_clinical_note_version(
                organization_id=scope["organization_id"],
                client_id=scope["client_id"],
                session_id=session_id,
            )
            if latest and latest["status"] == "finalized":
                note_id = latest["id"]
            elif latest:
                note = repository.finalize_clinical_note_draft(
                    organization_id=scope["organization_id"],
                    client_id=scope["client_id"],
                    session_id=session_id,
                    note_version_id=latest["id"],
                    actor_user_id=scope["actor_user_id"],
                )
                note_id = note["id"]
                synthesis_refresh.enqueue_insights_refresh(
                    connection,
                    organization_id=scope["organization_id"],
                    client_id=scope["client_id"],
                    event_type="clinical_note_amended" if note["parent_version_id"] else "clinical_note_finalized",
                    actor_user_id=scope["actor_user_id"],
                    target_type="clinical_note_version",
                    target_id=note_id,
                )
            else:
                sections = (session["content"] or {}).get("clinical_note") or []
                note_id = repository.create_clinical_note_version(
                    organization_id=scope["organization_id"],
                    client_id=scope["client_id"],
                    session_id=session_id,
                    content=note_content(sections),
                    status="finalized",
                    actor_user_id=scope["actor_user_id"],
                    source_synthesis_version_id=str(session["synthesis_id"]),
                )
                synthesis_refresh.enqueue_insights_refresh(
                    connection,
                    organization_id=scope["organization_id"],
                    client_id=scope["client_id"],
                    event_type="clinical_note_finalized",
                    actor_user_id=scope["actor_user_id"],
                    target_type="clinical_note_version",
                    target_id=note_id,
                )
        finalized_notes.append({"session_id": session_id, "note_version_id": str(note_id)})

    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT id, category, categories, content, session_id
                 FROM app.client_journey_entries
                WHERE organization_id=%s AND client_id=%s
                  AND session_id=ANY(%s) AND status='proposed'
                ORDER BY created_at, id""",
            (scope["organization_id"], scope["client_id"], session_ids),
        )
        proposals = cursor.fetchall()

    accepted = []
    for proposal in proposals:
        with connect() as connection:
            found = client_journey.review_entry(
                connection,
                organization_id=scope["organization_id"],
                client_id=scope["client_id"],
                entry_id=str(proposal["id"]),
                category=proposal["category"],
                categories=list(proposal["categories"]),
                content=proposal["content"],
                state="accepted",
                actor_user_id=scope["actor_user_id"],
            )
            if not found:
                raise RuntimeError(f"Evidence proposal disappeared before acceptance: {proposal['id']}")
            synthesis_refresh.enqueue_insights_refresh(
                connection,
                organization_id=scope["organization_id"],
                client_id=scope["client_id"],
                event_type="evidence_claim_accepted",
                actor_user_id=scope["actor_user_id"],
                target_type="client_journey_entry",
                target_id=str(proposal["id"]),
                metadata={"categories": list(proposal["categories"])},
            )
        accepted.append({"entry_id": str(proposal["id"]), "session_id": str(proposal["session_id"])})

    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT status, count(*) AS count FROM app.transcript_versions
                WHERE organization_id=%s AND client_id=%s AND session_id=ANY(%s)
                GROUP BY status ORDER BY status""",
            (scope["organization_id"], scope["client_id"], session_ids),
        )
        transcript_status = {row["status"]: row["count"] for row in cursor.fetchall()}
        cursor.execute(
            """SELECT status, count(*) AS count FROM app.client_journey_entries
                WHERE organization_id=%s AND client_id=%s AND session_id=ANY(%s)
                GROUP BY status ORDER BY status""",
            (scope["organization_id"], scope["client_id"], session_ids),
        )
        evidence_status = {row["status"]: row["count"] for row in cursor.fetchall()}
        cursor.execute(
            """SELECT status, count(*) AS count FROM app.clinical_note_versions
                WHERE organization_id=%s AND client_id=%s AND session_id=ANY(%s)
                GROUP BY status ORDER BY status""",
            (scope["organization_id"], scope["client_id"], session_ids),
        )
        note_status = {row["status"]: row["count"] for row in cursor.fetchall()}
        cursor.execute(
            """SELECT status, count(*) AS count FROM app.sessions
                WHERE organization_id=%s AND client_id=%s AND id=ANY(%s)
                GROUP BY status ORDER BY status""",
            (scope["organization_id"], scope["client_id"], session_ids),
        )
        session_status = {row["status"]: row["count"] for row in cursor.fetchall()}

    print(json.dumps({
        "finalized_transcripts": finalized_transcripts,
        "proposal_jobs": proposal_jobs,
        "proposal_job_statuses": proposal_job_statuses,
        "finalized_notes": finalized_notes,
        "accepted_claims": accepted,
        "transcript_status": transcript_status,
        "evidence_status": evidence_status,
        "note_status": note_status,
        "session_status": session_status,
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
