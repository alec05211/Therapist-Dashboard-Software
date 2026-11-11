"""Audit or prepare Avery Chen's explicitly synthetic Jeremy Heartwell case."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--sslrootcert", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    connection_args = {
        "host": args.host,
        "dbname": args.database,
        "user": args.username,
        "password": args.password,
        "sslmode": "verify-full",
        "sslrootcert": str(Path(args.sslrootcert).resolve()),
        "row_factory": dict_row,
    }
    with psycopg.connect(**connection_args) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT client.id AS client_id, client.organization_id,
                      practitioner.id AS practitioner_id, actor.id AS actor_user_id,
                      portal.id AS portal_id, portal.synthetic_case_key
                 FROM app.clients client
                 JOIN app.client_portal_accounts portal
                   ON portal.client_id=client.id AND portal.status='active'
                 JOIN app.client_therapist_access access
                   ON access.client_id=client.id AND access.organization_id=client.organization_id
                  AND access.revoked_at IS NULL AND access.can_manage_sessions
                  AND access.can_write_clinical
                 JOIN app.organization_practitioners practitioner
                   ON practitioner.id=access.practitioner_id AND practitioner.status='active'
                 JOIN app.organization_memberships membership
                   ON membership.id=practitioner.membership_id AND membership.status='active'
                 JOIN app.application_users actor
                   ON actor.id=membership.user_id AND actor.status='active'
                WHERE client.display_name='Avery Chen' AND client.status='active'
                  AND practitioner.professional_name='Jeremy Heartwell'"""
        )
        rows = cursor.fetchall()
        if len(rows) != 1:
            raise RuntimeError("Expected exactly one active Avery Chen and Jeremy Heartwell relationship.")
        context = rows[0]
        if context["synthetic_case_key"] not in {None, "heartwell-avery"}:
            raise RuntimeError("Avery's portal is already marked as a different synthetic case.")
        if args.apply and not context["synthetic_case_key"]:
            cursor.execute(
                "UPDATE app.client_portal_accounts SET synthetic_case_key='heartwell-avery' WHERE id=%s",
                (context["portal_id"],),
            )
            context["synthetic_case_key"] = "heartwell-avery"

        cursor.execute(
            """SELECT appointment.id AS appointment_id, appointment.starts_at,
                      appointment.ends_at, appointment.status AS appointment_status,
                      session.id AS session_id, session.status AS session_status,
                      job.runtime_id, job.status AS job_status,
                      transcript.id AS transcript_version_id,
                      transcript.status AS transcript_status,
                      note.id AS note_version_id, note.status AS note_status
                      , proposal.status AS proposal_job_status,
                      proposal.usage AS proposal_usage
                 FROM app.appointments appointment
                 LEFT JOIN app.sessions session ON session.appointment_id=appointment.id
                 LEFT JOIN app.session_storage_jobs job ON job.session_id=session.id
                 LEFT JOIN LATERAL (
                   SELECT id, status FROM app.transcript_versions
                    WHERE session_id=session.id ORDER BY version_number DESC LIMIT 1
                 ) transcript ON true
                 LEFT JOIN LATERAL (
                   SELECT id, status FROM app.clinical_note_versions
                    WHERE session_id=session.id ORDER BY version_number DESC LIMIT 1
                 ) note ON true
                 LEFT JOIN app.journey_proposal_analysis_jobs proposal
                   ON proposal.session_id=session.id
                WHERE appointment.organization_id=%s AND appointment.client_id=%s
                  AND appointment.primary_practitioner_id=%s
                ORDER BY appointment.starts_at""",
            (context["organization_id"], context["client_id"], context["practitioner_id"]),
        )
        appointments = cursor.fetchall()

    print(json.dumps({
        "applied": args.apply,
        "client_id": str(context["client_id"]),
        "organization_id": str(context["organization_id"]),
        "actor_user_id": str(context["actor_user_id"]),
        "synthetic_case_key": context["synthetic_case_key"],
        "appointments": appointments,
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
