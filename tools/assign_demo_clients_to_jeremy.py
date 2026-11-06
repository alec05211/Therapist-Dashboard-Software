"""Plan or apply Jeremy Heartwell relationships and recurring demo appointments."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row


TIMEZONE = "America/New_York"
SLOTS = {
    "Keisha Ward": (datetime(2026, 11, 10, 9, 0, tzinfo=ZoneInfo(TIMEZONE)), 1),
    "Luis Mendoza": (datetime(2026, 11, 10, 10, 30, tzinfo=ZoneInfo(TIMEZONE)), 1),
    "Owen Park": (datetime(2026, 11, 12, 13, 0, tzinfo=ZoneInfo(TIMEZONE)), 3),
    "Priya Nair": (datetime(2026, 11, 12, 14, 30, tzinfo=ZoneInfo(TIMEZONE)), 3),
}


def connection_arguments(args: argparse.Namespace) -> dict[str, str]:
    return {
        "host": args.host,
        "dbname": args.database,
        "user": args.username,
        "password": args.password,
        "sslmode": "verify-full",
        "sslrootcert": str(Path(args.sslrootcert).resolve()),
        "row_factory": dict_row,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--sslrootcert", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    changes: list[dict[str, object]] = []
    with psycopg.connect(**connection_arguments(args)) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT practitioner.id AS practitioner_id,
                      practitioner.organization_id, actor.id AS actor_user_id
               FROM app.organization_practitioners AS practitioner
               JOIN app.organization_memberships AS membership
                 ON membership.id=practitioner.membership_id
               JOIN app.application_users AS actor ON actor.id=membership.user_id
               WHERE practitioner.professional_name='Jeremy Heartwell'
                 AND practitioner.status='active' AND membership.status='active'
                 AND actor.status='active'"""
        )
        principals = cursor.fetchall()
        if len(principals) != 1:
            raise RuntimeError("Expected exactly one active Jeremy Heartwell practitioner.")
        principal = principals[0]

        cursor.execute(
            """SELECT id, auth0_subject, first_name, last_name, email
               FROM app.client_account_registrations
               WHERE status='pending' AND discoverable
               ORDER BY last_name, first_name
               FOR UPDATE"""
        )
        pending = cursor.fetchall()
        unknown = [f"{row['first_name']} {row['last_name']}" for row in pending
                   if f"{row['first_name']} {row['last_name']}" not in SLOTS]
        if unknown:
            raise RuntimeError(f"No reviewed schedule slot exists for: {', '.join(unknown)}")

        if args.apply:
            for registration in pending:
                name = f"{registration['first_name']} {registration['last_name']}"
                starts_at, weekday = SLOTS[name]
                occurrences = [starts_at + timedelta(weeks=index) for index in range(8)]
                for occurrence in occurrences:
                    ends_at = occurrence + timedelta(minutes=50)
                    cursor.execute(
                        """SELECT client.display_name
                           FROM app.appointments AS appointment
                           JOIN app.clients AS client ON client.id=appointment.client_id
                           WHERE appointment.primary_practitioner_id=%s
                             AND appointment.status IN ('scheduled','confirmed')
                             AND appointment.starts_at<%s AND appointment.ends_at>%s
                           LIMIT 1""",
                        (principal["practitioner_id"], ends_at, occurrence),
                    )
                    conflict = cursor.fetchone()
                    if conflict:
                        raise RuntimeError(
                            f"{name}'s proposed series overlaps {conflict['display_name']} at {occurrence}."
                        )

                cursor.execute(
                    """SELECT id FROM app.client_connection_invitations
                       WHERE registration_id=%s AND practitioner_id=%s AND status='pending'""",
                    (registration["id"], principal["practitioner_id"]),
                )
                invitation = cursor.fetchone()
                if not invitation:
                    cursor.execute(
                        """INSERT INTO app.client_connection_invitations
                             (registration_id, organization_id, practitioner_id, invited_by_user_id)
                           VALUES (%s,%s,%s,%s) RETURNING id""",
                        (registration["id"], principal["organization_id"],
                         principal["practitioner_id"], principal["actor_user_id"]),
                    )
                    invitation = cursor.fetchone()

                cursor.execute(
                    """INSERT INTO app.clients (organization_id, display_name, email, status)
                       VALUES (%s,%s,%s,'active') RETURNING id""",
                    (principal["organization_id"], name, registration["email"]),
                )
                client_id = cursor.fetchone()["id"]
                cursor.execute(
                    """INSERT INTO app.client_portal_accounts
                         (client_id, auth0_subject, display_name, status)
                       VALUES (%s,%s,%s,'active')""",
                    (client_id, registration["auth0_subject"], name),
                )
                cursor.execute(
                    """INSERT INTO app.client_portal_permissions (organization_id, client_id)
                       VALUES (%s,%s)""",
                    (principal["organization_id"], client_id),
                )
                cursor.execute(
                    """INSERT INTO app.client_therapist_access
                         (organization_id, client_id, practitioner_id, relationship_type,
                          can_read_clinical, can_write_clinical, can_view_artifacts,
                          can_manage_sessions, can_manage_client_access,
                          granted_by_user_id, grant_reason)
                       VALUES (%s,%s,%s,'primary',true,true,true,true,true,%s,
                               'Synthetic demo connection approved by product owner')""",
                    (principal["organization_id"], client_id, principal["practitioner_id"],
                     principal["actor_user_id"]),
                )
                cursor.execute(
                    """UPDATE app.client_account_registrations
                       SET status='connected', connected_client_id=%s WHERE id=%s""",
                    (client_id, registration["id"]),
                )
                cursor.execute(
                    """UPDATE app.client_connection_invitations
                       SET status=CASE WHEN id=%s THEN 'accepted' ELSE 'cancelled' END,
                           responded_at=CURRENT_TIMESTAMP
                       WHERE registration_id=%s AND status='pending'""",
                    (invitation["id"], registration["id"]),
                )
                cursor.execute(
                    """INSERT INTO app.client_scheduling_preferences
                         (organization_id, client_id, practitioner_id, cadence_weeks,
                          duration_minutes, meeting_mode, timezone, preferred_weekday,
                          preferred_start_local, updated_by_user_id)
                       VALUES (%s,%s,%s,1,50,'in_person',%s,%s,%s,%s)""",
                    (principal["organization_id"], client_id, principal["practitioner_id"],
                     TIMEZONE, weekday, starts_at.timetz().replace(tzinfo=None),
                     principal["actor_user_id"]),
                )
                series_id = uuid5(
                    NAMESPACE_URL,
                    f"therapist-dashboard/jeremy-heartwell/{name}/2026-11-recurring",
                )
                for occurrence in occurrences:
                    cursor.execute(
                        """INSERT INTO app.appointments
                             (organization_id, client_id, primary_practitioner_id,
                              starts_at, ends_at, status, appointment_type,
                              series_id, meeting_mode)
                           VALUES (%s,%s,%s,%s,%s,'scheduled','recurring',%s,'in_person')""",
                        (principal["organization_id"], client_id, principal["practitioner_id"],
                         occurrence, occurrence + timedelta(minutes=50), series_id),
                    )
                changes.append({
                    "client": name,
                    "client_id": str(client_id),
                    "relationship": "primary",
                    "first_session": starts_at.isoformat(),
                    "appointment_count": len(occurrences),
                })

        cursor.execute(
            """SELECT client.id, client.display_name, client.email, client.status,
                      COALESCE(json_agg(json_build_object(
                        'therapist', practitioner.professional_name,
                        'relationship_type', access.relationship_type,
                        'can_manage_sessions', access.can_manage_sessions
                      ) ORDER BY practitioner.professional_name)
                      FILTER (WHERE access.id IS NOT NULL), '[]'::json) AS relationships
               FROM app.clients AS client
               LEFT JOIN app.client_therapist_access AS access
                 ON access.client_id=client.id AND access.revoked_at IS NULL
               LEFT JOIN app.organization_practitioners AS practitioner
                 ON practitioner.id=access.practitioner_id
               WHERE client.status='active'
               GROUP BY client.id
               ORDER BY client.display_name"""
        )
        clients = cursor.fetchall()
        cursor.execute(
            """SELECT appointment.starts_at, appointment.ends_at,
                      client.display_name AS client
               FROM app.appointments AS appointment
               JOIN app.clients AS client ON client.id=appointment.client_id
               JOIN app.organization_practitioners AS practitioner
                 ON practitioner.id=appointment.primary_practitioner_id
               WHERE practitioner.professional_name='Jeremy Heartwell'
                 AND appointment.status IN ('scheduled','confirmed')
                 AND appointment.ends_at >= CURRENT_TIMESTAMP
               ORDER BY appointment.starts_at"""
        )
        jeremy_schedule = cursor.fetchall()
        cursor.execute(
            """SELECT registration.id AS registration_id,
                      trim(registration.first_name || ' ' || registration.last_name) AS name,
                      registration.email, registration.status,
                      registration.discoverable, registration.connected_client_id,
                      invitation.status AS invitation_status,
                      invitation.created_at AS invited_at, invitation.responded_at
               FROM app.client_account_registrations AS registration
               LEFT JOIN app.client_connection_invitations AS invitation
                 ON invitation.registration_id=registration.id
               ORDER BY registration.last_name, registration.first_name,
                        invitation.created_at DESC"""
        )
        registrations = cursor.fetchall()
        cursor.execute(
            """SELECT actor.display_name, actor.email, actor.status,
                      membership.role AS membership_role,
                      registration.status AS registration_status
               FROM app.application_users AS actor
               LEFT JOIN app.organization_memberships AS membership
                 ON membership.user_id=actor.id AND membership.status='active'
               LEFT JOIN app.client_account_registrations AS registration
                 ON registration.auth0_subject=actor.auth0_subject
               ORDER BY actor.display_name, actor.email"""
        )
        identities = cursor.fetchall()

    print(json.dumps({
        "applied": args.apply,
        "changes": changes,
        "pending_before_apply": [
            f"{row['first_name']} {row['last_name']}" for row in pending
        ],
        "clients": clients,
        "client_registrations": registrations,
        "identities": identities,
        "jeremy_future_schedule": jeremy_schedule,
    }, default=str, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
