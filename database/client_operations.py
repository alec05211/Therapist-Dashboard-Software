"""Minimal client-owned operational reads, independent of clinical retrieval."""
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Query, Response
from psycopg import Error as PsycopgError

from database.auth import validate_access_token
from database.connection import connect

router = APIRouter(prefix="/client-operations", tags=["client operations"])


def client_context(connection, authorization):
    claims = validate_access_token(authorization)
    with connection.cursor() as cursor:
        cursor.execute("""SELECT client.organization_id, client.id AS client_id
            FROM app.client_portal_accounts portal
            JOIN app.clients client ON client.id=portal.client_id
            JOIN app.organizations organization ON organization.id=client.organization_id
            WHERE portal.auth0_subject=%s AND portal.status='active'
              AND client.status='active' AND organization.status='active'""", (claims["sub"],))
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise HTTPException(403, "An unambiguous active client account is required.")
    return rows[0]


def read_scheduling(connection, context, *, limit=5):
    """Return the next appointments, using UTC offsets rather than guessing a timezone."""
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("Appointment limit must be an integer from 1 to 20.")
    with connection.cursor() as cursor:
        cursor.execute("""SELECT starts_at, ends_at, status, meeting_mode
            FROM app.appointments
            WHERE organization_id=%s AND client_id=%s
              AND status IN ('scheduled','confirmed') AND ends_at>CURRENT_TIMESTAMP
            ORDER BY starts_at, id LIMIT %s""",
            (context["organization_id"], context["client_id"], limit + 1))
        rows = cursor.fetchall()
    return {
        "status": "available", "source": "appointment_schedule",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "has_more": len(rows) > limit,
        "appointments": [{"starts_at": row["starts_at"].isoformat(),
                          "ends_at": row["ends_at"].isoformat(),
                          "status": row["status"], "meeting_mode": row["meeting_mode"]}
                         for row in rows[:limit]],
    }


def read_billing(connection, context):
    """Insurance on file is not a verified benefit or a billing ledger."""
    with connection.cursor() as cursor:
        cursor.execute("""SELECT status, model_extracted_fields, client_corrected_fields, updated_at
            FROM app.client_insurance_cards
            WHERE organization_id=%s AND client_id=%s AND status<>'replaced'
            ORDER BY created_at DESC LIMIT 1""", (context["organization_id"], context["client_id"]))
        row = cursor.fetchone()
    insurance = {"status": "not_on_file", "details": None, "benefits_verified": False}
    if row:
        corrected = row.get("client_corrected_fields")
        fields = corrected if isinstance(corrected, dict) else row.get("model_extracted_fields") or {}
        insurance = {
            "status": "available" if row["status"] == "ready" else "unavailable",
            "details": {key: fields.get(key) for key in (
                "payer_name", "plan_name", "member_services_phone", "behavioral_health_phone"
            )} if row["status"] == "ready" else None,
            "client_reviewed": isinstance(corrected, dict),
            "updated_at": row["updated_at"].isoformat(), "benefits_verified": False,
        }
    return {
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "source": "insurance_on_file",
        "insurance": insurance,
        "billing": {"status": "not_connected", "balance": None, "invoices": None,
                    "reason": "No invoice or payment ledger is connected. Amount owed is unknown."},
    }


def authorized_read(authorization, reader, **arguments):
    """Reauthorize each read, including model-requested reads; never accept client IDs."""
    try:
        with connect() as connection:
            context = client_context(connection, authorization)
            return reader(connection, context, **arguments)
    except PsycopgError as exc:
        raise HTTPException(503, "Operational information is temporarily unavailable.") from exc


@router.get("/scheduling")
def scheduling_information(response: Response, limit: int = Query(default=5, ge=1, le=20),
                           authorization: str | None = Header(default=None)):
    response.headers["Cache-Control"] = "no-store"
    return authorized_read(authorization, read_scheduling, limit=limit)


@router.get("/billing")
def billing_information(response: Response, authorization: str | None = Header(default=None)):
    response.headers["Cache-Control"] = "no-store"
    return authorized_read(authorization, read_billing)
