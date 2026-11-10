"""Prepare the explicitly synthetic Owen Park case for twelve historical uploads."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row


TIMEZONE = ZoneInfo("America/New_York")
FIRST_SESSION = datetime(2026, 8, 20, 13, 0, tzinfo=TIMEZONE)


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
                      access.id AS access_id, portal.id AS portal_id,
                      portal.synthetic_case_key
                 FROM app.clients client
                 JOIN app.client_portal_accounts portal
                   ON portal.client_id=client.id AND portal.status='active'
                 JOIN app.client_therapist_access access
                   ON access.client_id=client.id AND access.organization_id=client.organization_id
                  AND access.revoked_at IS NULL AND access.can_manage_sessions
                 JOIN app.organization_practitioners practitioner
                   ON practitioner.id=access.practitioner_id
                 JOIN app.organization_memberships membership
                   ON membership.id=practitioner.membership_id AND membership.status='active'
                 JOIN app.application_users actor
                   ON actor.id=membership.user_id AND actor.status='active'
                WHERE client.display_name='Owen Park' AND client.status='active'
                  AND practitioner.professional_name='Jeremy Heartwell'"""
        )
        rows = cursor.fetchall()
        if len(rows) != 1:
            raise RuntimeError("Expected exactly one active Owen Park and Jeremy Heartwell relationship.")
        context = rows[0]
        if args.apply and not context["synthetic_case_key"]:
            cursor.execute(
                "UPDATE app.client_portal_accounts SET synthetic_case_key='heartwell-owen' WHERE id=%s",
                (context["portal_id"],),
            )

        series_id = uuid5(NAMESPACE_URL, "therapist-dashboard/jeremy-heartwell/owen-park/2026-synthetic-history")
        appointments = []
        for index in range(12):
            number = index + 1
            appointment_id = uuid5(NAMESPACE_URL, f"therapist-dashboard/owen-park/session-{number:02d}")
            starts_at = FIRST_SESSION + timedelta(weeks=index)
            ends_at = starts_at + timedelta(minutes=50)
            if args.apply:
                cursor.execute(
                    """INSERT INTO app.appointments
                         (id, organization_id, client_id, primary_practitioner_id,
                          starts_at, ends_at, status, appointment_type, series_id, meeting_mode)
                       VALUES (%s,%s,%s,%s,%s,%s,'scheduled','recurring',%s,'in_person')
                       ON CONFLICT (id) DO UPDATE SET
                         starts_at=EXCLUDED.starts_at, ends_at=EXCLUDED.ends_at,
                         primary_practitioner_id=EXCLUDED.primary_practitioner_id,
                         series_id=EXCLUDED.series_id, updated_at=CURRENT_TIMESTAMP
                       WHERE app.appointments.organization_id=EXCLUDED.organization_id
                         AND app.appointments.client_id=EXCLUDED.client_id""",
                    (
                        appointment_id, context["organization_id"], context["client_id"],
                        context["practitioner_id"], starts_at, ends_at, series_id,
                    ),
                )
            cursor.execute(
                """SELECT appointment.id, appointment.starts_at, appointment.status,
                          job.runtime_id, job.status AS job_status
                     FROM app.appointments appointment
                     LEFT JOIN app.sessions session ON session.appointment_id=appointment.id
                     LEFT JOIN app.session_storage_jobs job ON job.session_id=session.id
                    WHERE appointment.id=%s""",
                (appointment_id,),
            )
            appointment = cursor.fetchone()
            appointments.append({key: str(value) if value is not None else None for key, value in appointment.items()})

    print(json.dumps({
        "applied": args.apply,
        "client_id": str(context["client_id"]),
        "organization_id": str(context["organization_id"]),
        "actor_user_id": str(context["actor_user_id"]),
        "synthetic_case_key": context["synthetic_case_key"] or ("heartwell-owen" if args.apply else None),
        "appointments": appointments,
    }, indent=2))


if __name__ == "__main__":
    main()
