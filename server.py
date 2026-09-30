"""Local recorder server backed by Amazon HealthScribe batch jobs."""
import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urlparse
from uuid import UUID, uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Body, FastAPI, File, Header, HTTPException, UploadFile, Request, status
from fastapi.responses import FileResponse, JSONResponse, Response
from psycopg import Error as PsycopgError
from psycopg.types.json import Json

from database.auth import validate_access_token
from database.connection import connect
from database import organization_storage
from database import client_journey
from database import speaker_identification
from database import document_workflow
from database.scheduling import available_recurring_slots, recurring_occurrences
from database.longitudinal_records import InsightEvidence, InsightItem, LongitudinalRecordRepository
from ai_harness.brief_projection import project_accepted_insights
from ai_harness.brief_service import brief_input
from ai_harness.pre_session import generate_openai_pre_session_brief, resolve_brief
from ai_harness.clinician_context import with_clinician_guidance
from pydantic import BaseModel, Field, field_validator

app = FastAPI()
app.include_router(document_workflow.router)
# Kept explicit so Uvicorn's local reload watcher reloads the application
# boundary when authentication behavior changes during development.
load_dotenv(Path(__file__).with_name(".env"))
# ORGANIZATION_STORAGE_ENABLED switches new uploads after verified provisioning.
RECORDINGS_DIRECTORY = Path(__file__).with_name("recordings")
MAX_AUDIO_UPLOAD_BYTES = 100 * 1024 * 1024
AUDIO_MIME_TYPES = {
    ".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
    ".mp4": "audio/mp4", ".flac": "audio/flac", ".ogg": "audio/ogg",
    ".webm": "audio/webm", ".amr": "audio/amr",
}
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
INPUT_BUCKET = os.getenv("HEALTHSCRIBE_INPUT_BUCKET")
OUTPUT_BUCKET = os.getenv("HEALTHSCRIBE_OUTPUT_BUCKET")
BATCH_ROLE_ARN = os.getenv("HEALTHSCRIBE_BATCH_DATA_ACCESS_ROLE_ARN")
POLL_SECONDS = max(1, int(os.getenv("HEALTHSCRIBE_POLL_SECONDS", "5")))
HEALTHSCRIBE_MAX_SPEAKERS = min(30, max(3, int(os.getenv("HEALTHSCRIBE_MAX_SPEAKERS", "6"))))


class TherapistOnboardingRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=200)
    professional_name: str = Field(min_length=1, max_length=200)
    practice_type: Literal["solo", "group"]
    team_setup: Literal["later", "now"]


class ClientOnboardingRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=254)
    discoverable: bool = True

    @field_validator("first_name", "last_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("Enter a valid name.")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value or None


class InvitationResponseRequest(BaseModel):
    action: Literal["accept", "decline"]


class ClientPortalPermissionsRequest(BaseModel):
    organization_id: str = Field(min_length=1, max_length=64)
    client_id: str = Field(min_length=1, max_length=64)
    # Session labels and dates are fixed client access. Retained for backwards-
    # compatible request parsing, but writes cannot disable it.
    can_view_session_history: bool = True
    can_view_shared_transcripts: bool
    can_view_insights: bool
    can_view_draft_notes: bool
    can_view_approved_summaries: bool = False
    can_play_shared_recordings: bool = False
    can_view_prescriptions: bool = False


class ParticipantIdentificationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    pronouns: str | None = Field(default=None, max_length=80)

    @field_validator("name")
    @classmethod
    def clean_identification_name(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("Control characters are not allowed.")
        return value

    @field_validator("pronouns")
    @classmethod
    def clean_identification_pronouns(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if any(ord(char) < 32 for char in value):
            raise ValueError("Control characters are not allowed.")
        return value or None

class SpeakerAssociationRequest(BaseModel):
    transcript_version_id: UUID
    source_label: str = Field(min_length=1, max_length=200)
    name: str = Field(default='', max_length=200)

    @field_validator('name', 'source_label')
    @classmethod
    def clean_text(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError('Control characters are not allowed.')
        return value.strip()


class ClientIdentificationRequest(BaseModel):
    organization_id: str = Field(min_length=1, max_length=64)
    client_id: str = Field(min_length=1, max_length=64)
    client: ParticipantIdentificationRequest
    therapist: ParticipantIdentificationRequest
    speakers: list[SpeakerAssociationRequest] = Field(default_factory=list, max_length=1000)


class SchedulingPreferencesRequest(BaseModel):
    organization_id: UUID
    client_id: UUID
    cadence_weeks: Literal[1, 2, 4] = 1
    duration_minutes: int = Field(default=50, ge=20, le=180)
    meeting_mode: Literal["in_person", "video", "phone"] = "in_person"
    timezone: str = Field(default="America/New_York", min_length=1, max_length=100)


class AppointmentCreateRequest(SchedulingPreferencesRequest):
    starts_at: datetime
    appointment_type: Literal["recurring", "make_up", "one_time"] = "one_time"
    recurrence_count: int = Field(default=1, ge=1, le=26)


class AppointmentUpdateRequest(BaseModel):
    organization_id: UUID
    client_id: UUID
    action: Literal["cancel", "reschedule"]
    starts_at: datetime | None = None
    duration_minutes: int = Field(default=50, ge=20, le=180)


@app.get("/identity/me")
def current_identity(authorization: str | None = Header(default=None)):
    """Return the application's role binding for the authenticated identity."""
    claims = validate_access_token(authorization)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT 'therapist' AS role, user_record.display_name
            FROM app.application_users AS user_record
            WHERE user_record.auth0_subject = %s AND user_record.status = 'active'
            UNION ALL
            SELECT 'client' AS role, portal.display_name
            FROM app.client_portal_accounts AS portal
            JOIN app.clients AS client ON client.id = portal.client_id
            WHERE portal.auth0_subject = %s AND portal.status = 'active' AND client.status = 'active'
            UNION ALL
            SELECT 'client_pending' AS role, registration.first_name || ' ' || registration.last_name AS display_name
            FROM app.client_account_registrations AS registration
            WHERE registration.auth0_subject = %s AND registration.status = 'pending'
            LIMIT 1
        """, (claims["sub"], claims["sub"], claims["sub"]))
        identity = cursor.fetchone()
    if not identity:
        return {"role": "unregistered", "displayName": claims.get("name") or "there"}
    return {"role": identity["role"], "displayName": identity["display_name"] or "there"}


PERMISSION_FIELDS = ("can_view_shared_transcripts", "can_view_insights", "can_view_draft_notes", "can_play_shared_recordings", "can_view_prescriptions")


@app.get("/therapist/clients")
def therapist_clients(authorization: str | None = Header(default=None)):
    """List clients through the signed-in practitioner's current access grants."""
    claims = validate_access_token(authorization)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT id FROM app.application_users
            WHERE auth0_subject=%s AND status='active'""", (claims["sub"],))
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="A therapist account is required.")
        cursor.execute("""SELECT DISTINCT client.id, client.organization_id,
                client.display_name AS name, client.email, client.phone, client.status,
                profile.photo IS NOT NULL AS has_photo
            FROM app.clients client
            JOIN app.client_portal_accounts portal
                ON portal.client_id=client.id AND portal.status='active'
            LEFT JOIN app.account_profiles profile ON profile.auth0_subject=portal.auth0_subject
            JOIN app.client_therapist_access access
                ON access.client_id=client.id AND access.organization_id=client.organization_id
            JOIN app.organization_practitioners practitioner
                ON practitioner.id=access.practitioner_id AND practitioner.organization_id=client.organization_id
            JOIN app.organization_memberships membership
                ON membership.id=practitioner.membership_id AND membership.organization_id=client.organization_id
            JOIN app.application_users actor ON actor.id=membership.user_id
            WHERE actor.auth0_subject=%s AND actor.status='active'
                AND membership.status='active' AND practitioner.status='active'
                AND client.status <> 'archived' AND client.archived_at IS NULL
                AND access.revoked_at IS NULL AND access.can_read_clinical
                AND access.effective_from <= CURRENT_TIMESTAMP
                AND (access.effective_until IS NULL OR access.effective_until > CURRENT_TIMESTAMP)
            ORDER BY client.display_name NULLS LAST, client.id""", (claims["sub"],))
        rows = cursor.fetchall()
    return {"clients": [{**row, "id": str(row["id"]), "organization_id": str(row["organization_id"]),
                          "photoUrl": f"/api/therapist/client-directory/{row['id']}/photo" if row["has_photo"] else None}
                         for row in rows]}


def therapist_principal(connection, authorization):
    claims = validate_access_token(authorization)
    with connection.cursor() as cursor:
        cursor.execute("""SELECT actor.id AS actor_user_id, practitioner.id AS practitioner_id,
                   practitioner.organization_id
            FROM app.application_users actor
            JOIN app.organization_memberships membership ON membership.user_id=actor.id
            JOIN app.organization_practitioners practitioner ON practitioner.membership_id=membership.id
            WHERE actor.auth0_subject=%s AND actor.status='active'
              AND membership.status='active' AND practitioner.status='active'""", (claims["sub"],))
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise HTTPException(status_code=403, detail="An unambiguous therapist account is required.")
    return rows[0]


@app.get("/therapist/client-directory")
def therapist_client_directory(query: str = "", authorization: str | None = Header(default=None)):
    with connect() as connection:
        principal = therapist_principal(connection, authorization)
        pattern = f"%{query.strip()}%"
        with connection.cursor() as cursor:
            cursor.execute("""SELECT client.id, client.display_name AS name, client.email, client.phone,
                       profile.photo IS NOT NULL AS has_photo, 'client' AS kind,
                       CASE WHEN EXISTS (SELECT 1 FROM app.client_therapist_access access
                           WHERE access.client_id=client.id AND access.practitioner_id=%s
                             AND access.revoked_at IS NULL)
                         THEN 'connected' ELSE 'available' END AS relationship
                FROM app.clients client
                JOIN app.client_portal_accounts portal ON portal.client_id=client.id
                LEFT JOIN app.account_profiles profile ON profile.auth0_subject=portal.auth0_subject
                WHERE client.organization_id=%s AND client.status='active' AND portal.status='active'
                  AND (%s='' OR client.display_name ILIKE %s OR COALESCE(client.email,'') ILIKE %s)
                UNION ALL
                SELECT registration.id, registration.first_name || ' ' || registration.last_name AS name,
                       registration.email, NULL AS phone, profile.photo IS NOT NULL AS has_photo,
                       'registration' AS kind, 'available' AS relationship
                FROM app.client_account_registrations registration
                LEFT JOIN app.account_profiles profile ON profile.auth0_subject=registration.auth0_subject
                WHERE registration.discoverable AND registration.status='pending' AND %s<>''
                  AND (registration.first_name ILIKE %s OR registration.last_name ILIKE %s
                       OR registration.first_name || ' ' || registration.last_name ILIKE %s
                       OR COALESCE(registration.email,'') ILIKE %s)
                  AND NOT EXISTS (SELECT 1 FROM app.client_connection_invitations invitation
                      WHERE invitation.registration_id=registration.id
                        AND invitation.practitioner_id=%s AND invitation.status='pending')
                ORDER BY name NULLS LAST LIMIT 30""",
                (principal["practitioner_id"], principal["organization_id"], query.strip(), pattern, pattern,
                 query.strip(), pattern, pattern, pattern, pattern, principal["practitioner_id"]))
            rows = cursor.fetchall()
    return {"clients": [{"id": str(row["id"]), "kind": row["kind"], "name": row["name"], "email": row["email"],
                         "phone": row["phone"], "relationship": row["relationship"],
                         "photoUrl": f"/api/therapist/client-directory/{row['id']}/photo" if row["has_photo"] else None}
                        for row in rows]}


@app.get("/therapist/client-directory/{client_id}/photo")
def therapist_directory_photo(client_id: UUID, authorization: str | None = Header(default=None)):
    with connect() as connection:
        principal = therapist_principal(connection, authorization)
        with connection.cursor() as cursor:
            cursor.execute("""SELECT profile.photo, profile.photo_mime FROM app.clients client
                JOIN app.client_portal_accounts portal ON portal.client_id=client.id
                JOIN app.account_profiles profile ON profile.auth0_subject=portal.auth0_subject
                WHERE client.id=%s AND client.organization_id=%s AND client.status='active'
                  AND portal.status='active'
                UNION ALL
                SELECT profile.photo, profile.photo_mime
                FROM app.client_account_registrations registration
                JOIN app.account_profiles profile ON profile.auth0_subject=registration.auth0_subject
                WHERE registration.id=%s AND registration.status='pending' AND registration.discoverable
                LIMIT 1""", (client_id, principal["organization_id"], client_id))
            row = cursor.fetchone()
    if not row or row["photo"] is None:
        raise HTTPException(status_code=404, detail="Photo not found.")
    return Response(content=bytes(row["photo"]), media_type=row["photo_mime"], headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.post("/therapist/clients/{client_id}", status_code=201)
def add_therapist_client(client_id: UUID, authorization: str | None = Header(default=None)):
    with connect() as connection:
        principal = therapist_principal(connection, authorization)
        with connection.cursor() as cursor:
            cursor.execute("""SELECT client.id, client.display_name AS name, client.email, client.phone
                FROM app.clients client JOIN app.client_portal_accounts portal ON portal.client_id=client.id
                WHERE client.id=%s AND client.organization_id=%s AND client.status='active'
                  AND portal.status='active' FOR UPDATE""", (client_id, principal["organization_id"]))
            client = cursor.fetchone()
            if not client:
                raise HTTPException(status_code=404, detail="Client account not found.")
            cursor.execute("""SELECT 1 FROM app.client_therapist_access
                WHERE client_id=%s AND practitioner_id=%s AND revoked_at IS NULL""",
                (client_id, principal["practitioner_id"]))
            if cursor.fetchone():
                raise HTTPException(status_code=409, detail="This client is already connected to your practice.")
            cursor.execute("""INSERT INTO app.client_therapist_access
                (organization_id, client_id, practitioner_id, relationship_type,
                 can_read_clinical, can_write_clinical, can_view_artifacts, can_manage_sessions,
                 can_manage_client_access, granted_by_user_id, grant_reason)
                VALUES (%s,%s,%s,'primary',true,true,true,true,true,%s,'Therapist added existing client account')""",
                (principal["organization_id"], client_id, principal["practitioner_id"], principal["actor_user_id"]))
    return {"client": {**client, "id": str(client["id"]), "organization_id": str(principal["organization_id"])}}


@app.post("/therapist/client-registrations/{registration_id}/invite", status_code=201)
def invite_registered_client(registration_id: UUID, authorization: str | None = Header(default=None)):
    with connect() as connection:
        principal = therapist_principal(connection, authorization)
        with connection.cursor() as cursor:
            cursor.execute("""SELECT id, first_name, last_name, email
                FROM app.client_account_registrations
                WHERE id=%s AND status='pending' AND discoverable""", (registration_id,))
            registration = cursor.fetchone()
            if not registration:
                raise HTTPException(status_code=404, detail="Client account not found.")
            display_name = f"{registration['first_name']} {registration['last_name']}"
            cursor.execute("""SELECT id FROM app.client_connection_invitations
                WHERE registration_id=%s AND practitioner_id=%s AND status='pending'""",
                (registration_id, principal["practitioner_id"]))
            invitation = cursor.fetchone()
            if not invitation:
                cursor.execute("""INSERT INTO app.client_connection_invitations
                    (registration_id, organization_id, practitioner_id, invited_by_user_id)
                    VALUES (%s,%s,%s,%s) RETURNING id""",
                    (registration_id, principal["organization_id"], principal["practitioner_id"],
                     principal["actor_user_id"]))
                invitation = cursor.fetchone()
    return {"invitation": {"id": str(invitation["id"]), "status": "pending",
                            "name": display_name, "email": registration["email"]}}


@app.get("/inbox")
def inbox(authorization: str | None = Header(default=None)):
    claims = validate_access_token(authorization)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT practitioner.id
            FROM app.application_users actor
            JOIN app.organization_memberships membership ON membership.user_id=actor.id
            JOIN app.organization_practitioners practitioner ON practitioner.membership_id=membership.id
            WHERE actor.auth0_subject=%s AND actor.status='active'
              AND membership.status='active' AND practitioner.status='active'""", (claims["sub"],))
        practitioners = cursor.fetchall()
        if len(practitioners) == 1:
            cursor.execute("""SELECT invitation.id, invitation.status, invitation.created_at,
                       registration.first_name || ' ' || registration.last_name AS counterpart_name,
                       registration.email AS counterpart_email, organization.name AS organization_name
                FROM app.client_connection_invitations invitation
                JOIN app.client_account_registrations registration ON registration.id=invitation.registration_id
                JOIN app.organizations organization ON organization.id=invitation.organization_id
                WHERE invitation.practitioner_id=%s
                ORDER BY invitation.created_at DESC""", (practitioners[0]["id"],))
            rows = cursor.fetchall()
            role = "therapist"
        else:
            cursor.execute("""SELECT id, status FROM app.client_account_registrations
                WHERE auth0_subject=%s""", (claims["sub"],))
            registration = cursor.fetchone()
            if not registration:
                return {"role": "unregistered", "unreadCount": 0, "invitations": []}
            cursor.execute("""SELECT invitation.id, invitation.status, invitation.created_at,
                       COALESCE(practitioner.professional_name, 'Your therapist') AS counterpart_name,
                       NULL::text AS counterpart_email, organization.name AS organization_name
                FROM app.client_connection_invitations invitation
                JOIN app.organization_practitioners practitioner ON practitioner.id=invitation.practitioner_id
                JOIN app.organizations organization ON organization.id=invitation.organization_id
                WHERE invitation.registration_id=%s
                ORDER BY invitation.created_at DESC""", (registration["id"],))
            rows = cursor.fetchall()
            role = "client" if registration["status"] == "connected" else "client_pending"
    invitations = [{**row, "id": str(row["id"]), "created_at": row["created_at"].isoformat()} for row in rows]
    return {"role": role, "unreadCount": sum(row["status"] == "pending" for row in rows) if role in ("client", "client_pending") else 0,
            "invitations": invitations}


@app.post("/inbox/invitations/{invitation_id}")
def respond_to_invitation(invitation_id: UUID, request: InvitationResponseRequest,
                          authorization: str | None = Header(default=None)):
    claims = validate_access_token(authorization)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT invitation.id, invitation.registration_id, invitation.organization_id,
                   invitation.practitioner_id, invitation.invited_by_user_id,
                   registration.auth0_subject, registration.first_name, registration.last_name, registration.email
            FROM app.client_connection_invitations invitation
            JOIN app.client_account_registrations registration ON registration.id=invitation.registration_id
            WHERE invitation.id=%s AND invitation.status='pending'
              AND registration.auth0_subject=%s AND registration.status='pending'
            FOR UPDATE""", (invitation_id, claims["sub"]))
        invitation = cursor.fetchone()
        if not invitation:
            raise HTTPException(status_code=404, detail="Pending invitation not found.")
        if request.action == "decline":
            cursor.execute("""UPDATE app.client_connection_invitations
                SET status='declined', responded_at=CURRENT_TIMESTAMP WHERE id=%s""", (invitation_id,))
            return {"status": "declined"}

        display_name = f"{invitation['first_name']} {invitation['last_name']}"
        cursor.execute("""INSERT INTO app.clients (organization_id, display_name, email, status)
            VALUES (%s,%s,%s,'active') RETURNING id""",
            (invitation["organization_id"], display_name, invitation["email"]))
        client = cursor.fetchone()
        cursor.execute("""INSERT INTO app.client_portal_accounts
            (client_id, auth0_subject, display_name, status) VALUES (%s,%s,%s,'active')""",
            (client["id"], invitation["auth0_subject"], display_name))
        cursor.execute("""INSERT INTO app.client_portal_permissions (organization_id, client_id)
            VALUES (%s,%s)""", (invitation["organization_id"], client["id"]))
        cursor.execute("""INSERT INTO app.client_therapist_access
            (organization_id, client_id, practitioner_id, relationship_type,
             can_read_clinical, can_write_clinical, can_view_artifacts, can_manage_sessions,
             can_manage_client_access, granted_by_user_id, grant_reason)
            VALUES (%s,%s,%s,'primary',true,true,true,true,true,%s,'Client accepted therapist invitation')""",
            (invitation["organization_id"], client["id"], invitation["practitioner_id"],
             invitation["invited_by_user_id"]))
        cursor.execute("""UPDATE app.client_account_registrations
            SET status='connected', connected_client_id=%s WHERE id=%s""",
            (client["id"], invitation["registration_id"]))
        cursor.execute("""UPDATE app.client_connection_invitations
            SET status=CASE WHEN id=%s THEN 'accepted' ELSE 'cancelled' END,
                responded_at=CURRENT_TIMESTAMP
            WHERE registration_id=%s AND status='pending'""",
            (invitation_id, invitation["registration_id"]))
    return {"status": "accepted", "clientId": str(client["id"])}


def read_portal_permissions(connection, context):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {', '.join(PERMISSION_FIELDS)} FROM app.client_portal_permissions WHERE organization_id=%s AND client_id=%s", (context["organization_id"], context["client_id"]))
        row = cursor.fetchone()
    return {"can_view_session_history": True,
            **{key: bool(row and row[key]) for key in PERMISSION_FIELDS}}


def resolve_sharing_context(connection, authorization, *, therapist=False, write=False):
    claims = validate_access_token(authorization)
    with connection.cursor() as cursor:
        if therapist:
            cursor.execute("""SELECT DISTINCT client.id AS client_id, client.organization_id
                FROM app.clients client
                JOIN app.client_portal_accounts portal ON portal.client_id=client.id
                JOIN app.client_therapist_access access ON access.client_id=client.id AND access.organization_id=client.organization_id
                JOIN app.organization_practitioners practitioner ON practitioner.id=access.practitioner_id
                JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id AND membership.organization_id=client.organization_id
                JOIN app.application_users actor ON actor.id=membership.user_id
                WHERE actor.auth0_subject=%s AND actor.status='active' AND membership.status='active'
                AND practitioner.status='active' AND client.status='active' AND portal.status='active'
                AND portal.synthetic_case_key='heartwell-sadic' AND access.revoked_at IS NULL
                AND access.effective_from <= CURRENT_TIMESTAMP
                AND (access.effective_until IS NULL OR access.effective_until > CURRENT_TIMESTAMP)
                AND access.can_read_clinical AND (NOT %s OR access.can_write_clinical)""", (claims["sub"], write))
        else:
            cursor.execute("""SELECT client.id AS client_id, client.organization_id
                FROM app.client_portal_accounts portal JOIN app.clients client ON client.id=portal.client_id
                WHERE portal.auth0_subject=%s AND portal.status='active' AND client.status='active'""",
                (claims["sub"],))
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise HTTPException(status_code=403, detail="No active linked client context is available.")
    return {key: str(value) for key, value in rows[0].items()}


def resolve_therapist_client_context(connection, authorization, client_id, *, write=False):
    principal = therapist_principal(connection, authorization)
    with connection.cursor() as cursor:
        cursor.execute("""SELECT client.id AS client_id, client.organization_id
            FROM app.clients client JOIN app.client_therapist_access access
              ON access.client_id=client.id AND access.organization_id=client.organization_id
            WHERE client.id=%s AND client.organization_id=%s AND client.status='active'
              AND access.practitioner_id=%s AND access.revoked_at IS NULL
              AND access.effective_from<=CURRENT_TIMESTAMP
              AND (access.effective_until IS NULL OR access.effective_until>CURRENT_TIMESTAMP)
              AND access.can_read_clinical AND (NOT %s OR access.can_write_clinical)""",
            (client_id, principal["organization_id"], principal["practitioner_id"], write))
        row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=403, detail="This client workspace is not available for your account.")
    return {key: str(value) for key, value in row.items()}


def scheduling_scope(connection, authorization, organization_id, client_id):
    """Resolve the signed-in therapist's active session-management grant."""
    claims = validate_access_token(authorization)
    with connection.cursor() as cursor:
        cursor.execute("""SELECT actor.id AS actor_user_id, practitioner.id AS practitioner_id,
                   client.display_name AS client_name
            FROM app.application_users actor
            JOIN app.organization_memberships membership ON membership.user_id=actor.id
            JOIN app.organization_practitioners practitioner ON practitioner.membership_id=membership.id
            JOIN app.client_therapist_access access ON access.practitioner_id=practitioner.id
            JOIN app.clients client ON client.id=access.client_id AND client.organization_id=access.organization_id
            WHERE actor.auth0_subject=%s AND actor.status='active'
              AND membership.status='active' AND practitioner.status='active'
              AND client.id=%s AND client.organization_id=%s AND client.status='active'
              AND access.revoked_at IS NULL AND access.can_manage_sessions
              AND access.effective_from<=CURRENT_TIMESTAMP
              AND (access.effective_until IS NULL OR access.effective_until>CURRENT_TIMESTAMP)""",
            (claims["sub"], client_id, organization_id))
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise HTTPException(status_code=403, detail="You do not have permission to manage this client's schedule.")
    return rows[0]


def appointment_payload(row):
    return {
        "id": str(row["id"]), "organization_id": str(row["organization_id"]),
        "client_id": str(row["client_id"]), "client_name": row.get("client_name"),
        "starts_at": row["starts_at"].isoformat(), "ends_at": row["ends_at"].isoformat(),
        "status": row["status"], "appointment_type": row["appointment_type"],
        "meeting_mode": row["meeting_mode"], "series_id": str(row["series_id"]) if row.get("series_id") else None,
    }


def scheduling_data(connection, context, scope):
    with connection.cursor() as cursor:
        cursor.execute("""SELECT cadence_weeks, duration_minutes, meeting_mode, timezone,
                   preferred_weekday, preferred_start_local
            FROM app.client_scheduling_preferences WHERE organization_id=%s AND client_id=%s
              AND practitioner_id=%s""", (context["organization_id"], context["client_id"], scope["practitioner_id"]))
        stored_preferences = cursor.fetchone()
        preferences = stored_preferences or {"cadence_weeks": 1, "duration_minutes": 50,
                                             "meeting_mode": "in_person", "timezone": "America/New_York",
                                             "preferred_weekday": None, "preferred_start_local": None}
        cursor.execute("""SELECT appointment.*, client.display_name AS client_name
            FROM app.appointments appointment JOIN app.clients client ON client.id=appointment.client_id
            WHERE appointment.organization_id=%s AND appointment.client_id=%s
              AND appointment.primary_practitioner_id=%s
            ORDER BY appointment.starts_at""", (context["organization_id"], context["client_id"], scope["practitioner_id"]))
        client_appointments = cursor.fetchall()
        cursor.execute("""SELECT starts_at, ends_at, meeting_mode FROM app.appointments
            WHERE organization_id=%s AND client_id=%s AND primary_practitioner_id=%s
              AND appointment_type='recurring' AND status IN ('scheduled','confirmed')
              AND ends_at>CURRENT_TIMESTAMP ORDER BY starts_at LIMIT 2""",
            (context["organization_id"], context["client_id"], scope["practitioner_id"]))
        recurring_appointments = cursor.fetchall()
        cursor.execute("""SELECT client_id, starts_at, ends_at, status FROM app.appointments
            WHERE organization_id=%s AND primary_practitioner_id=%s
              AND status IN ('scheduled','confirmed')
              AND ends_at>CURRENT_TIMESTAMP AND starts_at<CURRENT_TIMESTAMP + interval '36 weeks'""",
            (context["organization_id"], scope["practitioner_id"]))
        busy = cursor.fetchall()
    if not stored_preferences and recurring_appointments:
        first = recurring_appointments[0]
        cadence_weeks = 1
        if len(recurring_appointments) > 1:
            candidate = round((recurring_appointments[1]["starts_at"] - first["starts_at"]).days / 7)
            cadence_weeks = candidate if candidate in (1, 2, 4) else 1
        preferences = {"cadence_weeks": cadence_weeks,
                       "duration_minutes": round((first["ends_at"] - first["starts_at"]).total_seconds() / 60),
                       "meeting_mode": first["meeting_mode"], "timezone": "America/New_York",
                       "preferred_weekday": None, "preferred_start_local": None}
    preference_payload = dict(preferences)
    if preference_payload.get("preferred_start_local"):
        preference_payload["preferred_start_local"] = preference_payload["preferred_start_local"].isoformat()
    suggestions = available_recurring_slots(
        busy, timezone=preferences["timezone"], duration_minutes=preferences["duration_minutes"],
        cadence_weeks=preferences["cadence_weeks"], occurrences=8,
    )
    return {"organization_id": str(context["organization_id"]), "client_id": str(context["client_id"]),
            "client_name": scope["client_name"], "preferences": preference_payload,
            "has_existing_schedule": bool(stored_preferences or recurring_appointments),
            "current_recurring_starts_at": recurring_appointments[0]["starts_at"].isoformat() if recurring_appointments else None,
            "appointments": [appointment_payload(row) for row in client_appointments],
            "busy_times": [{"starts_at": row["starts_at"].isoformat(),
                            "ends_at": row["ends_at"].isoformat()} for row in busy
                           if str(row["client_id"]) != str(context["client_id"])],
            "suggestions": suggestions}


@app.get("/calendar/appointments")
def calendar_appointments(start: datetime, end: datetime, authorization: str | None = Header(default=None)):
    if end <= start or end - start > timedelta(days=62):
        raise HTTPException(status_code=400, detail="Choose a calendar range of up to 62 days.")
    claims = validate_access_token(authorization)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT DISTINCT appointment.*, client.display_name AS client_name
            FROM app.appointments appointment
            JOIN app.clients client ON client.id=appointment.client_id
            JOIN app.client_therapist_access access ON access.client_id=client.id
              AND access.organization_id=client.organization_id
              AND access.practitioner_id=appointment.primary_practitioner_id
            JOIN app.organization_practitioners practitioner ON practitioner.id=access.practitioner_id
            JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id
            JOIN app.application_users actor ON actor.id=membership.user_id
            WHERE actor.auth0_subject=%s AND actor.status='active' AND membership.status='active'
              AND practitioner.status='active' AND access.revoked_at IS NULL AND access.can_manage_sessions
              AND appointment.starts_at<%s AND appointment.ends_at>%s
            ORDER BY appointment.starts_at""", (claims["sub"], end, start))
        rows = cursor.fetchall()
    return {"appointments": [appointment_payload(row) for row in rows]}


@app.get("/client-scheduling")
def get_client_scheduling(client_id: str | None = None, authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = resolve_therapist_client_context(connection, authorization, client_id) if client_id else resolve_sharing_context(connection, authorization, therapist=True)
        scope = scheduling_scope(connection, authorization, **context)
        return scheduling_data(connection, context, scope)


@app.put("/client-scheduling/preferences")
def update_scheduling_preferences(request: SchedulingPreferencesRequest, authorization: str | None = Header(default=None)):
    context = {"organization_id": str(request.organization_id), "client_id": str(request.client_id)}
    with connect() as connection:
        scope = scheduling_scope(connection, authorization, **context)
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO app.client_scheduling_preferences
                (organization_id, client_id, practitioner_id, cadence_weeks, duration_minutes,
                 meeting_mode, timezone, updated_by_user_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (client_id) DO UPDATE SET cadence_weeks=EXCLUDED.cadence_weeks,
                  duration_minutes=EXCLUDED.duration_minutes, meeting_mode=EXCLUDED.meeting_mode,
                  timezone=EXCLUDED.timezone, updated_by_user_id=EXCLUDED.updated_by_user_id,
                  updated_at=CURRENT_TIMESTAMP""", (request.organization_id, request.client_id,
                    scope["practitioner_id"], request.cadence_weeks, request.duration_minutes,
                    request.meeting_mode, request.timezone, scope["actor_user_id"]))
        return scheduling_data(connection, context, scope)


@app.post("/client-scheduling/appointments", status_code=201)
def create_appointment(request: AppointmentCreateRequest, authorization: str | None = Header(default=None)):
    context = {"organization_id": str(request.organization_id), "client_id": str(request.client_id)}
    with connect() as connection:
        scope = scheduling_scope(connection, authorization, **context)
        starts = recurring_occurrences(request.starts_at, request.cadence_weeks,
                                       request.recurrence_count if request.appointment_type == "recurring" else 1)
        series_id = uuid4() if len(starts) > 1 else None
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(scope["practitioner_id"]),))
            for starts_at in starts:
                ends_at = starts_at + timedelta(minutes=request.duration_minutes)
                cursor.execute("""SELECT 1 FROM app.appointments WHERE primary_practitioner_id=%s
                    AND status IN ('scheduled','confirmed') AND starts_at<%s AND ends_at>%s LIMIT 1""",
                    (scope["practitioner_id"], ends_at, starts_at))
                if cursor.fetchone():
                    raise HTTPException(status_code=409, detail="That time overlaps another appointment.")
            cursor.execute("""INSERT INTO app.client_scheduling_preferences
                (organization_id, client_id, practitioner_id, cadence_weeks, duration_minutes,
                 meeting_mode, timezone, updated_by_user_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (client_id) DO UPDATE SET cadence_weeks=EXCLUDED.cadence_weeks,
                  duration_minutes=EXCLUDED.duration_minutes, meeting_mode=EXCLUDED.meeting_mode,
                  timezone=EXCLUDED.timezone, updated_by_user_id=EXCLUDED.updated_by_user_id,
                  updated_at=CURRENT_TIMESTAMP""", (request.organization_id, request.client_id,
                    scope["practitioner_id"], request.cadence_weeks, request.duration_minutes,
                    request.meeting_mode, request.timezone, scope["actor_user_id"]))
            for starts_at in starts:
                cursor.execute("""INSERT INTO app.appointments
                    (organization_id, client_id, primary_practitioner_id, starts_at, ends_at,
                     status, appointment_type, series_id, meeting_mode)
                    VALUES (%s,%s,%s,%s,%s,'scheduled',%s,%s,%s)""",
                    (request.organization_id, request.client_id, scope["practitioner_id"], starts_at,
                     starts_at + timedelta(minutes=request.duration_minutes), request.appointment_type,
                     series_id, request.meeting_mode))
        return scheduling_data(connection, context, scope)


@app.patch("/client-scheduling/appointments/{appointment_id}")
def update_appointment(appointment_id: UUID, request: AppointmentUpdateRequest,
                       authorization: str | None = Header(default=None)):
    context = {"organization_id": str(request.organization_id), "client_id": str(request.client_id)}
    with connect() as connection:
        scope = scheduling_scope(connection, authorization, **context)
        with connection.cursor() as cursor:
            cursor.execute("""SELECT * FROM app.appointments WHERE id=%s AND organization_id=%s
                AND client_id=%s AND primary_practitioner_id=%s FOR UPDATE""",
                (appointment_id, request.organization_id, request.client_id, scope["practitioner_id"]))
            appointment = cursor.fetchone()
            if not appointment:
                raise HTTPException(status_code=404, detail="Appointment not found.")
            if request.action == "cancel":
                cursor.execute("""UPDATE app.appointments SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP,
                    cancelled_by_user_id=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s""",
                    (scope["actor_user_id"], appointment_id))
            else:
                if request.starts_at is None:
                    raise HTTPException(status_code=422, detail="A new start time is required.")
                ends_at = request.starts_at + timedelta(minutes=request.duration_minutes)
                cursor.execute("""SELECT 1 FROM app.appointments WHERE primary_practitioner_id=%s
                    AND id<>%s AND status IN ('scheduled','confirmed') AND starts_at<%s AND ends_at>%s LIMIT 1""",
                    (scope["practitioner_id"], appointment_id, ends_at, request.starts_at))
                if cursor.fetchone():
                    raise HTTPException(status_code=409, detail="That time overlaps another appointment.")
                cursor.execute("""UPDATE app.appointments SET starts_at=%s, ends_at=%s,
                    updated_at=CURRENT_TIMESTAMP WHERE id=%s""", (request.starts_at, ends_at, appointment_id))
        return scheduling_data(connection, context, scope)


class AccountProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    pronouns: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    about_me: str | None = Field(default=None, max_length=2000)
    discoverable: bool | None = None

    @field_validator("name", "first_name", "last_name", "pronouns", "email", "phone", "about_me")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if any(ord(char) < 32 for char in value):
            raise ValueError("Control characters are not allowed.")
        return value or None

    @field_validator("email")
    @classmethod
    def email_shape(cls, value: str | None) -> str | None:
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid contact email.")
        return value


def account_profile_target(connection, authorization):
    claims = validate_access_token(authorization)
    with connection.cursor() as cursor:
        cursor.execute("""SELECT DISTINCT practitioner.id, practitioner.professional_name AS name,
                practitioner.contact_email AS email, practitioner.contact_phone AS phone
                FROM app.application_users actor
                JOIN app.organization_memberships membership ON membership.user_id=actor.id
                JOIN app.organization_practitioners practitioner ON practitioner.membership_id=membership.id
                WHERE actor.auth0_subject=%s AND actor.status='active'
                  AND membership.status='active' AND membership.starts_at<=CURRENT_TIMESTAMP
                  AND (membership.ends_at IS NULL OR membership.ends_at>CURRENT_TIMESTAMP)
                  AND practitioner.status='active'""", (claims["sub"],))
        rows = cursor.fetchall()
        if len(rows) > 1:
            raise HTTPException(status_code=403, detail="An unambiguous active account profile is not available.")
        if rows:
            return "therapist", claims["sub"], rows[0]
        cursor.execute("""SELECT client.id, client.display_name AS name, client.email, client.phone
            FROM app.client_portal_accounts portal JOIN app.clients client ON client.id=portal.client_id
            WHERE portal.auth0_subject=%s AND portal.status='active' AND client.status='active'""",
            (claims["sub"],))
        rows = cursor.fetchall()
        if len(rows) > 1:
            raise HTTPException(status_code=403, detail="An unambiguous active account profile is not available.")
        if rows:
            return "client", claims["sub"], rows[0]
        cursor.execute("""SELECT id, first_name || ' ' || last_name AS name,
                   first_name, last_name, email, NULL::text AS phone, discoverable
            FROM app.client_account_registrations
            WHERE auth0_subject=%s AND status='pending'""", (claims["sub"],))
        registration = cursor.fetchone()
        if registration:
            return "client_pending", claims["sub"], registration
    return "unregistered", claims["sub"], {
        "id": None, "name": claims.get("name") or "", "first_name": claims.get("given_name"),
        "last_name": claims.get("family_name"), "email": claims.get("email"),
        "phone": None, "discoverable": True,
    }


@app.get("/account/profile")
def get_account_profile(authorization: str | None = Header(default=None)):
    with connect() as connection:
        role, subject, target = account_profile_target(connection, authorization)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pronouns, about_me, photo IS NOT NULL AS has_photo FROM app.account_profiles WHERE auth0_subject=%s", (subject,))
            extras = cursor.fetchone() or {}
    name = target["name"] or ""
    name_parts = name.split(maxsplit=1)
    return {"role": role, "name": name,
            "firstName": target.get("first_name") or (name_parts[0] if name_parts else ""),
            "lastName": target.get("last_name") or (name_parts[1] if len(name_parts) > 1 else ""),
            "pronouns": extras.get("pronouns"), "email": target["email"],
            "phone": target["phone"], "aboutMe": extras.get("about_me") if role == "therapist" else None,
            "discoverable": target.get("discoverable") if role in ("client_pending", "unregistered") else None,
            "photoUrl": "/api/account/profile/photo" if extras.get("has_photo") else None}


@app.put("/account/profile")
def update_account_profile(request: AccountProfileUpdate, authorization: str | None = Header(default=None)):
    with connect() as connection:
        role, subject, target = account_profile_target(connection, authorization)
        if role != "therapist" and request.about_me is not None:
            raise HTTPException(status_code=403, detail="About me is not enabled for client accounts.")
        with connection.cursor() as cursor:
            if role == "therapist":
                cursor.execute("""UPDATE app.organization_practitioners
                    SET professional_name=%s, contact_email=%s, contact_phone=%s
                    WHERE id=%s""", (request.name, request.email, request.phone, target["id"]))
            elif role == "client":
                cursor.execute("UPDATE app.clients SET display_name=%s, email=%s, phone=%s WHERE id=%s",
                    (request.name, request.email, request.phone, target["id"]))
                cursor.execute("UPDATE app.client_portal_accounts SET display_name=%s WHERE client_id=%s",
                    (request.name, target["id"]))
            else:
                first_name = request.first_name or ""
                last_name = request.last_name or ""
                if not first_name or not last_name:
                    raise HTTPException(status_code=422, detail="Enter your first and last name.")
                cursor.execute("""INSERT INTO app.client_account_registrations
                    (auth0_subject, first_name, last_name, email, discoverable, status)
                    VALUES (%s,%s,%s,%s,%s,'pending')
                    ON CONFLICT (auth0_subject) DO UPDATE SET first_name=EXCLUDED.first_name,
                      last_name=EXCLUDED.last_name, email=EXCLUDED.email,
                      discoverable=EXCLUDED.discoverable, status='pending', connected_client_id=NULL""",
                    (subject, first_name, last_name, request.email,
                     request.discoverable if request.discoverable is not None else target.get("discoverable", True)))
            cursor.execute("""INSERT INTO app.account_profiles (auth0_subject, pronouns, about_me) VALUES (%s,%s,%s)
                ON CONFLICT (auth0_subject) DO UPDATE SET
                  pronouns=EXCLUDED.pronouns, about_me=EXCLUDED.about_me""",
                (subject, request.pronouns, request.about_me if role == "therapist" else None))
    return get_account_profile(authorization)


def valid_photo(data: bytes, mime: str) -> bool:
    return (mime == "image/jpeg" and data.startswith(b"\xff\xd8\xff")) or \
           (mime == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or \
           (mime == "image/webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP")


@app.put("/account/profile/photo")
async def update_account_photo(photo: UploadFile = File(...), authorization: str | None = Header(default=None)):
    mime = (photo.content_type or "").lower()
    data = await photo.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024 or not valid_photo(data, mime):
        raise HTTPException(status_code=400, detail="Choose a JPEG, PNG, or WebP image under 2 MB.")
    with connect() as connection:
        _, subject, _ = account_profile_target(connection, authorization)
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO app.account_profiles (auth0_subject, photo, photo_mime) VALUES (%s,%s,%s)
                ON CONFLICT (auth0_subject) DO UPDATE SET photo=EXCLUDED.photo, photo_mime=EXCLUDED.photo_mime""",
                (subject, data, mime))
    return {"photoUrl": "/api/account/profile/photo"}


@app.delete("/account/profile/photo")
def delete_account_photo(authorization: str | None = Header(default=None)):
    with connect() as connection:
        _, subject, _ = account_profile_target(connection, authorization)
        with connection.cursor() as cursor:
            cursor.execute("UPDATE app.account_profiles SET photo=NULL, photo_mime=NULL WHERE auth0_subject=%s", (subject,))
    return {"photoUrl": None}


@app.get("/account/profile/photo")
def account_photo(authorization: str | None = Header(default=None)):
    with connect() as connection:
        _, subject, _ = account_profile_target(connection, authorization)
        with connection.cursor() as cursor:
            cursor.execute("SELECT photo, photo_mime FROM app.account_profiles WHERE auth0_subject=%s", (subject,))
            row = cursor.fetchone()
    if not row or row["photo"] is None:
        raise HTTPException(status_code=404, detail="Photo not found.")
    return Response(content=bytes(row["photo"]), media_type=row["photo_mime"], headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.get("/relationship-profile/photo")
def relationship_photo(client_id: str | None = None, authorization: str | None = Header(default=None)):
    identity = current_identity(authorization)
    therapist = identity["role"] == "therapist"
    with connect() as connection:
        context = resolve_therapist_client_context(connection, authorization, client_id) if therapist and client_id else resolve_sharing_context(connection, authorization, therapist=therapist)
        with connection.cursor() as cursor:
            if therapist:
                cursor.execute("""SELECT portal.auth0_subject FROM app.client_portal_accounts portal
                    WHERE portal.client_id=%s AND portal.status='active'""", (context["client_id"],))
            else:
                cursor.execute("""SELECT DISTINCT actor.auth0_subject FROM app.client_therapist_access access
                    JOIN app.organization_practitioners practitioner ON practitioner.id=access.practitioner_id
                    JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id
                    JOIN app.application_users actor ON actor.id=membership.user_id
                    WHERE access.client_id=%s AND access.organization_id=%s AND access.revoked_at IS NULL
                      AND access.effective_from<=CURRENT_TIMESTAMP
                      AND (access.effective_until IS NULL OR access.effective_until>CURRENT_TIMESTAMP)
                      AND access.can_read_clinical
                      AND practitioner.status='active' AND membership.status='active' AND actor.status='active'""",
                    (context["client_id"], context["organization_id"]))
            rows = cursor.fetchall()
            if len(rows) != 1:
                raise HTTPException(status_code=403, detail="An unambiguous active care profile is not available.")
            cursor.execute("SELECT photo, photo_mime FROM app.account_profiles WHERE auth0_subject=%s", (rows[0]["auth0_subject"],))
            row = cursor.fetchone()
    if not row or row["photo"] is None:
        raise HTTPException(status_code=404, detail="Photo not found.")
    return Response(content=bytes(row["photo"]), media_type=row["photo_mime"], headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.get("/relationship-profile")
def relationship_profile(authorization: str | None = Header(default=None), client_id: str | None = None):
    identity = current_identity(authorization)
    therapist = identity["role"] == "therapist"
    with connect() as connection:
        context = resolve_therapist_client_context(connection, authorization, client_id) if therapist and client_id else resolve_sharing_context(connection, authorization, therapist=therapist)
        with connection.cursor() as cursor:
            if therapist:
                cursor.execute("""SELECT client.display_name AS name, client.email, client.phone, portal.auth0_subject, portal.synthetic_case_key
                    FROM app.clients client JOIN app.client_portal_accounts portal ON portal.client_id=client.id
                    WHERE client.id=%s AND client.organization_id=%s AND client.status='active' AND portal.status='active'""",
                    (context["client_id"], context["organization_id"]))
            else:
                cursor.execute("""SELECT DISTINCT practitioner.id, practitioner.professional_name AS name,
                    practitioner.contact_email AS email, practitioner.contact_phone AS phone, actor.auth0_subject
                    FROM app.client_therapist_access access
                    JOIN app.organization_practitioners practitioner ON practitioner.id=access.practitioner_id
                      AND practitioner.organization_id=access.organization_id
                    JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id
                      AND membership.organization_id=access.organization_id
                    JOIN app.application_users actor ON actor.id=membership.user_id
                    WHERE access.client_id=%s AND access.organization_id=%s
                      AND access.revoked_at IS NULL AND access.effective_from<=CURRENT_TIMESTAMP
                      AND (access.effective_until IS NULL OR access.effective_until>CURRENT_TIMESTAMP)
                      AND access.can_read_clinical AND practitioner.status='active'
                      AND membership.status='active' AND membership.starts_at<=CURRENT_TIMESTAMP
                      AND (membership.ends_at IS NULL OR membership.ends_at>CURRENT_TIMESTAMP)
                      AND actor.status='active'""", (context["client_id"], context["organization_id"]))
            rows = cursor.fetchall()
    if len(rows) != 1:
        raise HTTPException(status_code=403, detail="An unambiguous active care profile is not available.")
    row = rows[0]
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT photo IS NOT NULL AS has_photo, about_me FROM app.account_profiles WHERE auth0_subject=%s", (row["auth0_subject"],))
        extras = cursor.fetchone() or {}
    role = "Client" if therapist else "Therapist"
    name = row["name"] or role
    profile = {"name": name, "role": role, "initials": "".join(part[0] for part in name.split()[:2]).upper(),
            "email": row["email"], "phone": row["phone"],
            "imageSrc": f"/api/relationship-profile/photo?client_id={context['client_id']}" if therapist and extras.get("has_photo") else "/api/relationship-profile/photo" if extras.get("has_photo") else None,
            "aboutMe": extras.get("about_me") if not therapist else None}
    if therapist:
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("""SELECT EXISTS (SELECT 1 FROM app.client_scheduling_preferences preference
                    WHERE preference.organization_id=%s AND preference.client_id=%s)
                OR EXISTS (SELECT 1 FROM app.appointments appointment
                    WHERE appointment.organization_id=%s AND appointment.client_id=%s
                      AND appointment.status IN ('scheduled','confirmed')) AS configured""",
                (context["organization_id"], context["client_id"], context["organization_id"], context["client_id"]))
            configured_row = cursor.fetchone() or {}
            configured = bool(configured_row.get("configured"))
        profile.update(organizationId=context["organization_id"], clientId=context["client_id"],
                       syntheticCase=row.get("synthetic_case_key") == "heartwell-sadic",
                       needsSetup=not configured)
    return profile


@app.get("/client-portal-permissions")
def get_client_portal_permissions(client_id: str, authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = resolve_therapist_client_context(connection, authorization, client_id)
        return {**context, **read_portal_permissions(connection, context)}


@app.put("/client-portal-permissions")
def update_client_portal_permissions(request: ClientPortalPermissionsRequest, authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = resolve_therapist_client_context(connection, authorization, request.client_id, write=True)
        if context != {"organization_id": request.organization_id, "client_id": request.client_id}:
            raise HTTPException(status_code=403, detail="The requested client is not your linked client.")
        actor = authorize_clinical_access(connection, authorization=authorization, **context, require_write=True)
        columns = ', '.join(PERMISSION_FIELDS)
        updates = ', '.join(f"{key}=EXCLUDED.{key}" for key in PERMISSION_FIELDS)
        with connection.cursor() as cursor:
            cursor.execute(f"""INSERT INTO app.client_portal_permissions
                (organization_id, client_id, {columns}, updated_by_user_id)
                VALUES ({", ".join(["%s"] * (len(PERMISSION_FIELDS) + 3))}) ON CONFLICT (client_id) DO UPDATE SET
                {updates}, updated_by_user_id=EXCLUDED.updated_by_user_id
                WHERE app.client_portal_permissions.organization_id=EXCLUDED.organization_id
                RETURNING {columns}""", (request.organization_id, request.client_id, *(getattr(request, key) for key in PERMISSION_FIELDS), actor))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="Client organization does not match.")
        return {**context, "can_view_session_history": True, **row}


def identification_sample(cursor, context, display_name, speaker_prefix):
    """Find a brief review excerpt without creating or comparing voiceprints."""
    cursor.execute("""SELECT job.runtime_id, job.storage->>'audio_key' AS audio_key,
            sample.starts_at_seconds, sample.ends_at_seconds
        FROM app.session_storage_jobs job
        JOIN app.sessions session ON session.id=job.session_id
        JOIN app.transcript_versions transcript
          ON transcript.session_id=session.id AND transcript.organization_id=session.organization_id
          AND transcript.client_id=session.client_id AND transcript.status <> 'superseded'
        JOIN app.transcript_speaker_samples sample ON sample.transcript_version_id=transcript.id
        JOIN app.transcript_segments segment ON segment.id=sample.transcript_segment_id
        LEFT JOIN app.transcript_speaker_labels label
          ON label.transcript_version_id=transcript.id AND label.source_label=segment.speaker_label
        WHERE job.organization_id=%s AND job.client_id=%s AND job.status='COMPLETED'
          AND (lower(trim(label.display_label))=lower(trim(%s))
               OR (label.display_label IS NULL AND upper(segment.speaker_label) IN (%s, %s)))
          AND NOT EXISTS (
            SELECT 1 FROM app.transcript_versions newer
            WHERE newer.session_id=transcript.session_id
              AND newer.version_number>transcript.version_number
              AND newer.status <> 'superseded')
        ORDER BY COALESCE(session.started_at, transcript.created_at) DESC
        LIMIT 1""", (context["organization_id"], context["client_id"], display_name, speaker_prefix, f"{speaker_prefix}_0"))
    row = cursor.fetchone()
    if not row or not row["audio_key"]:
        return None
    start = float(row["starts_at_seconds"])
    end = float(row["ends_at_seconds"])
    return {"recordingUrl": f"/api/recordings/{row['runtime_id']}/{Path(row['audio_key']).name}?client_id={context['client_id']}",
            "start": start, "end": end}


def read_client_identification(connection, context, actor_user_id):
    with connection.cursor() as cursor:
        cursor.execute("""SELECT client.display_name AS client_name,
                practitioner.professional_name AS therapist_name
            FROM app.clients client
            JOIN app.client_therapist_access access
              ON access.client_id=client.id AND access.organization_id=client.organization_id
            JOIN app.organization_practitioners practitioner ON practitioner.id=access.practitioner_id
            JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id
            WHERE client.id=%s AND client.organization_id=%s AND membership.user_id=%s
              AND access.revoked_at IS NULL AND practitioner.status='active'
            LIMIT 1""", (context["client_id"], context["organization_id"], actor_user_id))
        relationship = cursor.fetchone()
        if not relationship:
            raise HTTPException(status_code=404, detail="Client identification is unavailable.")
        cursor.execute("""SELECT participant_role, display_name
            FROM app.client_identification_profiles
            WHERE organization_id=%s AND client_id=%s""",
            (context["organization_id"], context["client_id"]))
        saved = {row["participant_role"]: row for row in cursor.fetchall()}
        client_name = saved.get("client", {}).get("display_name") or relationship["client_name"] or "Client"
        therapist_name = saved.get("therapist", {}).get("display_name") or relationship["therapist_name"] or "Therapist"
        client_sample = identification_sample(cursor, context, client_name, "PATIENT")
        therapist_sample = identification_sample(cursor, context, therapist_name, "CLINICIAN")
        speakers = speaker_identification.list_associations(cursor, context,
            {'client': client_name, 'therapist': therapist_name})
    return {**context,
        "client": {"name": client_name, "pronouns": saved.get("client", {}).get("pronouns"), "sample": client_sample},
        "therapist": {"name": therapist_name, "pronouns": saved.get("therapist", {}).get("pronouns"), "sample": therapist_sample}, "speakers": speakers}


@app.get("/client-identification")
def get_client_identification(client_id: str, authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = resolve_therapist_client_context(connection, authorization, client_id)
        actor = authorize_clinical_access(connection, authorization=authorization, **context, require_write=False)
        return read_client_identification(connection, context, actor)


@app.put("/client-identification")
def update_client_identification(request: ClientIdentificationRequest, authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = resolve_therapist_client_context(connection, authorization, request.client_id, write=True)
        if context != {"organization_id": request.organization_id, "client_id": request.client_id}:
            raise HTTPException(status_code=403, detail="The requested client is not your linked client.")
        actor = authorize_clinical_access(connection, authorization=authorization, **context, require_write=True)
        with connection.cursor() as cursor:
            try:
                speaker_identification.save_associations(cursor, context, request.speakers, actor)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            for role, participant in (("client", request.client), ("therapist", request.therapist)):
                cursor.execute("""INSERT INTO app.client_identification_profiles
                    (organization_id, client_id, participant_role, display_name, pronouns, updated_by_user_id)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (client_id, participant_role) DO UPDATE SET
                      organization_id=EXCLUDED.organization_id,
                      display_name=EXCLUDED.display_name,
                      pronouns=EXCLUDED.pronouns,
                      updated_by_user_id=EXCLUDED.updated_by_user_id,
                      updated_at=CURRENT_TIMESTAMP""",
                    (context["organization_id"], context["client_id"], role, participant.name, participant.pronouns, actor))
        return read_client_identification(connection, context, actor)


def shared_session_materials(context, permissions):
    # Explicit allowlist: never include arbitrary runtime recordings or provider metadata.
    materials = []
    for job in organization_storage.completed_job_records(context):
        needs_clinical_material = permissions["can_view_shared_transcripts"] or permissions["can_view_draft_notes"]
        data = organization_storage.session_review.read_result(job["storage"]) if needs_clinical_material else {}
        data = data or {}
        session_id = job["runtime_id"]
        item = {"id": session_id, "label": job["label"], "created_at": job["created_at"].isoformat()}
        if permissions["can_view_shared_transcripts"]:
            item["segments"] = [{"speaker": data.get("speakers", {}).get(segment.get("speaker"), segment.get("speaker", "")), "text": segment.get("text", ""), "start": segment.get("start", 0), "end": segment.get("end", 0)} for segment in data.get("segments", [])]
        if permissions["can_play_shared_recordings"] and permissions["can_view_shared_transcripts"]:
            item["recording_url"] = f"/client-portal/sessions/{session_id}/recording"
        if permissions["can_view_draft_notes"]:
            item["draft_note"] = data.get("clinical_note", [])
        materials.append(item)
    return materials


@app.get("/client-portal")
def client_portal(authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = resolve_sharing_context(connection, authorization)
        permissions = read_portal_permissions(connection, context)
        result = {"permissions": permissions,
                  "sessions": shared_session_materials(context, permissions)}
        with connection.cursor() as cursor:
            cursor.execute("""SELECT appointment.*, client.display_name AS client_name
                FROM app.appointments appointment
                JOIN app.clients client ON client.id=appointment.client_id
                  AND client.organization_id=appointment.organization_id
                WHERE appointment.organization_id=%s AND appointment.client_id=%s
                  AND appointment.status IN ('scheduled','confirmed')
                  AND appointment.ends_at>CURRENT_TIMESTAMP
                ORDER BY appointment.starts_at""",
                (context["organization_id"], context["client_id"]))
            result["appointments"] = [appointment_payload(row) for row in cursor.fetchall()]
        if permissions["can_view_insights"]:
            with connection.cursor() as cursor:
                cursor.execute("""SELECT item.content->>'text' AS text FROM app.longitudinal_insight_items item
                    JOIN app.longitudinal_insight_snapshots snapshot ON snapshot.id=item.snapshot_id
                    WHERE snapshot.id=(SELECT id FROM app.longitudinal_insight_snapshots
                        WHERE organization_id=%s AND client_id=%s ORDER BY version_number DESC LIMIT 1)
                    AND snapshot.status='accepted' AND item.review_state='accepted'
                    ORDER BY item.display_order""", (context["organization_id"], context["client_id"]))
                result["insights"] = [row["text"] for row in cursor.fetchall() if row["text"]]
        return result


@app.get("/client-portal/sessions/{session_id}/recording")
def shared_session_recording(session_id: str, authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = resolve_sharing_context(connection, authorization)
        permissions = read_portal_permissions(connection, context)
        if not (permissions["can_play_shared_recordings"] and permissions["can_view_shared_transcripts"]):
            raise HTTPException(status_code=403, detail="Recording playback is not shared.")
    job = organization_storage.find_job(context, session_id)
    if not job or job["status"] != "COMPLETED":
        raise HTTPException(status_code=404, detail="Shared recording not found.")
    filename = Path(job["storage"]["audio_key"]).name
    try:
        path = organization_storage.restore_artifact(job["storage"], filename, session_directory(session_id))
    except (FileNotFoundError, BotoCoreError, ClientError) as exc:
        raise HTTPException(status_code=404, detail="Shared recording not found.") from exc
    return FileResponse(path, media_type=AUDIO_MIME_TYPES.get(path.suffix.lower(), "application/octet-stream"), filename=filename, headers={"Cache-Control": "no-store"})


@app.middleware("http")
async def protect_legacy_clinical_routes(request: Request, call_next):
    # The old filesystem API is therapist-only, including direct backend requests.
    path = request.scope["path"]
    if path.startswith(("/transcripts", "/recordings")) or path == "/transcribe":
        try:
            with connect() as connection:
                client_id = request.query_params.get("client_id")
                if not client_id:
                    raise HTTPException(status_code=422, detail="A client workspace is required.")
                context = resolve_therapist_client_context(connection, request.headers.get("authorization"), client_id, write=request.method not in ("GET", "HEAD"))
                request.state.care_context = context
            parts = path.strip("/").split("/")
            if len(parts) > 1 and parts[0] in ("transcripts", "recordings") and re.fullmatch(r"session-[0-9a-f-]{36}", parts[1], re.IGNORECASE):
                job = organization_storage.find_job(context, parts[1].lower())
                if not job:
                    raise HTTPException(status_code=404, detail="Session not found.")
                request.state.storage_job = job
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers={"Cache-Control": "no-store"})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


class ClinicalNoteVersionRequest(BaseModel):
    organization_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=1, max_length=64)
    content: dict[str, Any]
    status: Literal["draft", "reviewed", "finalized"] = "draft"
    source_synthesis_version_id: str | None = Field(default=None, max_length=64)
    parent_version_id: str | None = Field(default=None, max_length=64)


class LongitudinalEvidenceRequest(BaseModel):
    transcript_segment_id: str | None = Field(default=None, max_length=64)
    clinical_note_version_id: str | None = Field(default=None, max_length=64)
    evidence_role: Literal["supporting", "contrasting", "context"] = "supporting"


class LongitudinalInsightItemRequest(BaseModel):
    item_kind: Literal[
        "trajectory", "theme", "open_thread", "relevant_history", "client_context", "therapist_curated"
    ]
    content: dict[str, Any]
    evidence: list[LongitudinalEvidenceRequest]
    review_state: Literal["draft", "accepted", "hidden", "stale", "disputed"] = "draft"
    display_order: int = Field(default=0, ge=0)


class LongitudinalInsightSnapshotRequest(BaseModel):
    organization_id: str = Field(min_length=1, max_length=64)
    content: dict[str, Any]
    items: list[LongitudinalInsightItemRequest]
    generator_name: str = Field(min_length=1, max_length=120)
    generator_version: str | None = Field(default=None, max_length=120)
    selection_policy_version: str = Field(min_length=1, max_length=120)
    source_cutoff_session_id: str | None = Field(default=None, max_length=64)
    parent_snapshot_id: str | None = Field(default=None, max_length=64)


class JourneyReviewRequest(BaseModel):
    organization_id: str = Field(min_length=1, max_length=64)
    category: Literal['context', 'theme', 'important_quote', 'resolution', 'breakthrough', 'open_thread']
    text: str = Field(min_length=1, max_length=4000)
    status: Literal['accepted', 'rejected', 'hidden', 'stale', 'disputed']


def authorize_clinical_access(
    connection: Any,
    *,
    authorization: str | None,
    organization_id: str,
    client_id: str,
    require_write: bool,
) -> str:
    """Resolve a therapist's active, client-specific clinical permission."""
    claims = validate_access_token(authorization)
    permission = "access.can_write_clinical" if require_write else "access.can_read_clinical"
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT app_user.id
            FROM app.application_users AS app_user
            JOIN app.organization_memberships AS membership
              ON membership.user_id = app_user.id
            JOIN app.organization_practitioners AS practitioner
              ON practitioner.membership_id = membership.id
            JOIN app.client_therapist_access AS access
              ON access.practitioner_id = practitioner.id
             AND access.organization_id = membership.organization_id
            WHERE app_user.auth0_subject = %s
              AND app_user.status = 'active'
              AND membership.organization_id = %s
              AND membership.status = 'active'
              AND practitioner.status = 'active'
              AND access.client_id = %s
              AND access.revoked_at IS NULL
              AND access.effective_from <= CURRENT_TIMESTAMP
              AND (access.effective_until IS NULL OR access.effective_until > CURRENT_TIMESTAMP)
              AND {permission}
            LIMIT 1
            """,
            (claims["sub"], organization_id, client_id),
        )
        user = cursor.fetchone()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have active clinical access to this client.",
        )
    return str(user["id"])


@app.get("/healthz")
def healthz():
    """Process health check; deliberately does not disclose dependencies."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    """Readiness check for private operational validation."""
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except (RuntimeError, PsycopgError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The service is not ready.",
        ) from exc
    return {"status": "ready"}


def configuration() -> tuple[str, str, str]:
    missing = [name for name, value in {
        "HEALTHSCRIBE_INPUT_BUCKET": INPUT_BUCKET,
        "HEALTHSCRIBE_OUTPUT_BUCKET": OUTPUT_BUCKET,
        "HEALTHSCRIBE_BATCH_DATA_ACCESS_ROLE_ARN": BATCH_ROLE_ARN,
    }.items() if not value]
    if missing:
        raise RuntimeError(f"Missing HealthScribe configuration: {', '.join(missing)}")
    return INPUT_BUCKET or "", OUTPUT_BUCKET or "", BATCH_ROLE_ARN or ""


def session_directory(session_id: str) -> Path:
    return RECORDINGS_DIRECTORY / Path(session_id).name


def transcript_path(session_id: str) -> Path:
    return session_directory(session_id) / "transcript.json"


def status_path(session_id: str) -> Path:
    return session_directory(session_id) / "healthscribe-status.json"


def write_json(path: Path, content: dict[str, Any]) -> None:
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")


@app.post("/onboarding/therapist", status_code=status.HTTP_201_CREATED)
def onboard_therapist(
    request: TherapistOnboardingRequest,
    authorization: str | None = Header(default=None),
):
    """Create the first organization and owner-practitioner membership."""
    claims = validate_access_token(authorization)
    auth0_subject = claims["sub"]

    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO app.application_users (auth0_subject, display_name)
                    VALUES (%s, %s)
                    ON CONFLICT (auth0_subject) DO UPDATE
                      SET display_name = EXCLUDED.display_name,
                          updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                    """,
                    (auth0_subject, request.professional_name.strip()),
                )
                user = cursor.fetchone()
                if not user:
                    raise RuntimeError("Could not create the application user.")

                cursor.execute(
                    """
                    SELECT membership.organization_id, organization.name
                    FROM app.organization_memberships AS membership
                    JOIN app.organizations AS organization
                      ON organization.id = membership.organization_id
                    WHERE membership.user_id = %s
                      AND membership.role = 'owner'
                      AND membership.status = 'active'
                    ORDER BY membership.created_at
                    LIMIT 1
                    """,
                    (user["id"],),
                )
                existing = cursor.fetchone()
                if existing:
                    return {
                        "created": False,
                        "organization_id": str(existing["organization_id"]),
                        "organization_name": existing["name"],
                    }

                cursor.execute(
                    """
                    INSERT INTO app.organizations (name, settings)
                    VALUES (%s, %s)
                    RETURNING id, name
                    """,
                    (
                        request.organization_name.strip(),
                        Json({
                            "practice_type": request.practice_type,
                            "team_setup": request.team_setup,
                        }),
                    ),
                )
                organization = cursor.fetchone()
                if not organization:
                    raise RuntimeError("Could not create the organization.")

                cursor.execute(
                    """
                    INSERT INTO app.organization_memberships (
                      organization_id, user_id, role, status
                    )
                    VALUES (%s, %s, 'owner', 'active')
                    RETURNING id
                    """,
                    (organization["id"], user["id"]),
                )
                membership = cursor.fetchone()
                if not membership:
                    raise RuntimeError("Could not create the organization membership.")

                cursor.execute(
                    """
                    INSERT INTO app.organization_practitioners (
                      organization_id, membership_id, professional_name, status
                    )
                    VALUES (%s, %s, %s, 'active')
                    RETURNING id
                    """,
                    (
                        organization["id"],
                        membership["id"],
                        request.professional_name.strip(),
                    ),
                )
                practitioner = cursor.fetchone()
                if not practitioner:
                    raise RuntimeError("Could not create the practitioner profile.")

                cursor.execute(
                    """
                    INSERT INTO app.audit_events (
                      organization_id, actor_user_id, action, target_type,
                      target_id, outcome, metadata
                    )
                    VALUES (%s, %s, 'organization.created', 'organization', %s,
                            'allowed', %s)
                    """,
                    (
                        organization["id"],
                        user["id"],
                        organization["id"],
                        Json({
                            "practice_type": request.practice_type,
                            "team_setup": request.team_setup,
                            "practitioner_id": str(practitioner["id"]),
                        }),
                    ),
                )

            connection.commit()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PsycopgError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is temporarily unavailable.",
        ) from exc

    return {
        "created": True,
        "organization_id": str(organization["id"]),
        "organization_name": organization["name"],
        "membership_id": str(membership["id"]),
        "practitioner_id": str(practitioner["id"]),
    }


@app.post("/onboarding/client", status_code=status.HTTP_201_CREATED)
def onboard_client(
    request: ClientOnboardingRequest,
    authorization: str | None = Header(default=None),
):
    """Register an Auth0 identity for explicit therapist directory discovery."""
    claims = validate_access_token(authorization)
    subject = claims["sub"]
    display_name = f"{request.first_name} {request.last_name}"
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM app.application_users WHERE auth0_subject=%s AND status='active'", (subject,))
            if cursor.fetchone():
                raise HTTPException(status_code=409, detail="This sign-in already belongs to a therapist account.")
            cursor.execute("""SELECT portal.client_id
                FROM app.client_portal_accounts portal
                WHERE portal.auth0_subject=%s AND portal.status='active'""", (subject,))
            portal = cursor.fetchone()
            if portal:
                cursor.execute("""UPDATE app.clients SET display_name=%s, email=%s
                    WHERE id=%s RETURNING id""", (display_name, request.email, portal["client_id"]))
                client = cursor.fetchone()
                cursor.execute("UPDATE app.client_portal_accounts SET display_name=%s WHERE client_id=%s",
                    (display_name, portal["client_id"]))
                cursor.execute("""INSERT INTO app.client_account_registrations
                    (auth0_subject, first_name, last_name, email, discoverable, status, connected_client_id)
                    VALUES (%s,%s,%s,%s,%s,'connected',%s)
                    ON CONFLICT (auth0_subject) DO UPDATE SET first_name=EXCLUDED.first_name,
                      last_name=EXCLUDED.last_name, email=EXCLUDED.email,
                      discoverable=EXCLUDED.discoverable, status='connected',
                      connected_client_id=EXCLUDED.connected_client_id""",
                    (subject, request.first_name, request.last_name, request.email,
                     request.discoverable, portal["client_id"]))
                return {"created": False, "connected": True, "name": display_name, "client_id": str(client["id"])}

            cursor.execute("""INSERT INTO app.client_account_registrations
                (auth0_subject, first_name, last_name, email, discoverable, status)
                VALUES (%s,%s,%s,%s,%s,'pending')
                ON CONFLICT (auth0_subject) DO UPDATE SET first_name=EXCLUDED.first_name,
                  last_name=EXCLUDED.last_name, email=EXCLUDED.email,
                  discoverable=EXCLUDED.discoverable, status='pending', connected_client_id=NULL
                RETURNING id""",
                (subject, request.first_name, request.last_name, request.email, request.discoverable))
            registration = cursor.fetchone()
    return {"created": True, "connected": False, "name": display_name,
            "registration_id": str(registration["id"])}


@app.post("/clinical-records/clients/{client_id}/note-versions", status_code=status.HTTP_201_CREATED)
def create_clinical_note_version(
    client_id: str,
    request: ClinicalNoteVersionRequest,
    authorization: str | None = Header(default=None),
):
    """Append a therapist-owned note revision after client-specific authorization."""
    try:
        with connect() as connection:
            actor_user_id = authorize_clinical_access(
                connection,
                authorization=authorization,
                organization_id=request.organization_id,
                client_id=client_id,
                require_write=True,
            )
            record_id = LongitudinalRecordRepository(connection).create_clinical_note_version(
                organization_id=request.organization_id,
                client_id=client_id,
                session_id=request.session_id,
                content=request.content,
                status=request.status,
                actor_user_id=actor_user_id,
                source_synthesis_version_id=request.source_synthesis_version_id,
                parent_version_id=request.parent_version_id,
            )
            connection.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The database is temporarily unavailable.") from exc
    except PsycopgError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The database is temporarily unavailable.") from exc
    return {"id": record_id, "status": request.status}


@app.post("/clinical-records/clients/{client_id}/insight-snapshots", status_code=status.HTTP_201_CREATED)
def create_longitudinal_insight_snapshot(
    client_id: str,
    request: LongitudinalInsightSnapshotRequest,
    authorization: str | None = Header(default=None),
):
    """Save an evidence-linked longitudinal draft for therapist review.

    This endpoint never marks a generated item accepted. Acceptance remains a
    separate clinician action that will be added with the review UI.
    """
    try:
        items = tuple(
            InsightItem(
                item_kind=item.item_kind,
                content=item.content,
                evidence=tuple(
                    InsightEvidence(
                        transcript_segment_id=evidence.transcript_segment_id,
                        clinical_note_version_id=evidence.clinical_note_version_id,
                        evidence_role=evidence.evidence_role,
                    )
                    for evidence in item.evidence
                ),
                review_state=item.review_state,
                display_order=item.display_order,
            )
            for item in request.items
        )
        with connect() as connection:
            actor_user_id = authorize_clinical_access(
                connection,
                authorization=authorization,
                organization_id=request.organization_id,
                client_id=client_id,
                require_write=True,
            )
            record_id = LongitudinalRecordRepository(connection).create_insight_snapshot(
                organization_id=request.organization_id,
                client_id=client_id,
                content=request.content,
                items=items,
                generator_name=request.generator_name,
                generator_version=request.generator_version,
                selection_policy_version=request.selection_policy_version,
                actor_user_id=actor_user_id,
                source_cutoff_session_id=request.source_cutoff_session_id,
                parent_snapshot_id=request.parent_snapshot_id,
            )
            connection.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The database is temporarily unavailable.") from exc
    except PsycopgError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The database is temporarily unavailable.") from exc
    return {"id": record_id, "status": "draft"}


@app.get('/clinical-records/clients/{client_id}/journey-entries')
def get_client_journey_entries(client_id: str, organization_id: str, authorization: str | None = Header(default=None)):
    """Read source-linked model proposals and therapist decisions for one client."""
    try:
        with connect() as connection:
            authorize_clinical_access(connection, authorization=authorization,
                                      organization_id=organization_id, client_id=client_id, require_write=False)
            return {'entries': client_journey.list_entries(connection, organization_id, client_id)}
    except (RuntimeError, PsycopgError) as exc:
        raise HTTPException(status_code=503, detail='The database is temporarily unavailable.') from exc


@app.put('/clinical-records/clients/{client_id}/journey-entries/{entry_id}')
def review_client_journey_entry(client_id: str, entry_id: str, request: JourneyReviewRequest,
                                authorization: str | None = Header(default=None)):
    """A therapist's explicit review decision controls future brief inclusion."""
    try:
        with connect() as connection:
            actor = authorize_clinical_access(connection, authorization=authorization,
                                              organization_id=request.organization_id, client_id=client_id,
                                              require_write=True)
            found = client_journey.review_entry(connection, organization_id=request.organization_id,
                                                client_id=client_id, entry_id=entry_id, category=request.category,
                                                content=request.text, state=request.status, actor_user_id=actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (RuntimeError, PsycopgError) as exc:
        raise HTTPException(status_code=503, detail='The database is temporarily unavailable.') from exc
    if not found:
        raise HTTPException(status_code=404, detail='Journey entry not found for this client.')
    return {'id': entry_id, 'status': request.status}


@app.get("/clinical-records/clients/{client_id}/pre-session-context")
def get_pre_session_context_packet(
    client_id: str,
    organization_id: str,
    authorization: str | None = Header(default=None),
):
    """Return accepted insights and source-linked clinician guidance for synthesis."""
    try:
        with connect() as connection:
            authorize_clinical_access(
                connection,
                authorization=authorization,
                organization_id=organization_id,
                client_id=client_id,
                require_write=False,
            )
            packet = LongitudinalRecordRepository(connection).build_pre_session_context_packet(
                organization_id=organization_id,
                client_id=client_id,
            )
            packet = with_clinician_guidance(packet, client_journey.list_entries(
                connection, organization_id, client_id, status='accepted'))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The database is temporarily unavailable.") from exc
    except PsycopgError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The database is temporarily unavailable.") from exc
    if packet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No accepted longitudinal context is available for this client.")
    return packet


@app.get("/clinical-records/clients/{client_id}/pre-session-brief")
def get_current_pre_session_brief(
    client_id: str,
    organization_id: str,
    authorization: str | None = Header(default=None),
):
    """Read the latest accepted client history as a cited, current review draft."""
    try:
        with connect() as connection:
            authorize_clinical_access(connection, authorization=authorization,
                                      organization_id=organization_id, client_id=client_id, require_write=False)
            packet = LongitudinalRecordRepository(connection).build_pre_session_context_packet(
                organization_id=organization_id, client_id=client_id)
            journey = client_journey.list_entries(connection, organization_id, client_id, status='accepted')
    except (RuntimeError, PsycopgError) as exc:
        raise HTTPException(status_code=503, detail='The database is temporarily unavailable.') from exc
    if not packet and not journey:
        raise HTTPException(status_code=404, detail='No therapist-approved insight history is available for this client.')
    fallback = project_accepted_insights(packet, journey)
    fingerprint, request = brief_input(fallback)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('app.generated_pre_session_briefs') AS relation")
        if not cursor.fetchone()["relation"]:
            return fallback
        cursor.execute("SELECT response FROM app.generated_pre_session_briefs WHERE organization_id=%s AND client_id=%s AND context_hash=%s",
                       (organization_id, client_id, fingerprint))
        saved = cursor.fetchone()
    if saved:
        try:
            return resolve_brief(saved['response'], request['evidence'])
        except ValueError:
            pass  # Invalid or obsolete output cannot produce claim links.
    return fallback


@app.post("/clinical-records/clients/{client_id}/pre-session-brief/generate")
def generate_current_pre_session_brief(client_id: str, organization_id: str, authorization: str | None = Header(default=None)):
    with connect() as connection:
        actor = authorize_clinical_access(connection, authorization=authorization, organization_id=organization_id, client_id=client_id, require_write=True)
        packet = LongitudinalRecordRepository(connection).build_pre_session_context_packet(organization_id=organization_id, client_id=client_id)
        journey = client_journey.list_entries(connection, organization_id, client_id, status='accepted')
    # Explicit deployment approval; never implicitly send all clients to a provider.
    allowed = os.getenv('PRE_SESSION_MODEL_APPROVED_CLIENT_IDS', '').split(',')
    if client_id not in allowed:
        raise HTTPException(status_code=503, detail='Model processing is not configured for this client.')
    key, model = os.getenv('OPENAI_API_KEY'), os.getenv('PRE_SESSION_MODEL')
    if not key or not model:
        raise HTTPException(status_code=503, detail='Pre-session model credentials and model must be configured.')
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('app.generated_pre_session_briefs') AS relation")
        if not cursor.fetchone()['relation']:
            raise HTTPException(status_code=503, detail='Apply the generated-brief database migration before generation.')
    fallback = project_accepted_insights(packet, journey)
    fingerprint, request = brief_input(fallback)
    if not request['evidence']:
        raise HTTPException(status_code=409, detail='No accepted evidence is available.')
    try:
        generated, metadata = generate_openai_pre_session_brief(synthesis_request=request, api_key=key, model=model)
        resolved = resolve_brief(generated, request['evidence'])
    except (RuntimeError, ValueError):
        raise HTTPException(status_code=502, detail='The model did not return a valid cited brief. Existing context was retained.')
    with connect() as connection:
        authorize_clinical_access(connection, authorization=authorization, organization_id=organization_id, client_id=client_id, require_write=True)
        current_packet = LongitudinalRecordRepository(connection).build_pre_session_context_packet(organization_id=organization_id, client_id=client_id)
        current_journey = client_journey.list_entries(connection, organization_id, client_id, status='accepted')
        if brief_input(project_accepted_insights(current_packet, current_journey))[0] != fingerprint:
            raise HTTPException(status_code=409, detail='Accepted context changed during generation. Generate again using the current context.')
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO app.generated_pre_session_briefs
                (organization_id, client_id, context_hash, response, model, generated_by)
                VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (organization_id, client_id)
                DO UPDATE SET context_hash=EXCLUDED.context_hash, response=EXCLUDED.response,
                model=EXCLUDED.model, generated_by=EXCLUDED.generated_by, generated_at=CURRENT_TIMESTAMP""",
                (organization_id, client_id, fingerprint, Json(generated), metadata['model'], actor))
    return resolved


@app.get("/clinical-records/clients/{client_id}/insight-snapshots/latest")
def get_latest_longitudinal_insight_snapshot(
    client_id: str,
    organization_id: str,
    authorization: str | None = Header(default=None),
):
    """Return the latest evidence-linked workspace for an authorized therapist."""
    try:
        with connect() as connection:
            authorize_clinical_access(
                connection,
                authorization=authorization,
                organization_id=organization_id,
                client_id=client_id,
                require_write=False,
            )
            snapshot = LongitudinalRecordRepository(connection).get_latest_insight_snapshot(
                organization_id=organization_id,
                client_id=client_id,
            )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The database is temporarily unavailable.") from exc
    except PsycopgError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The database is temporarily unavailable.") from exc
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No longitudinal workspace is available for this client.")
    return snapshot


def s3_location(uri: str) -> tuple[str, str]:
    """Resolve both S3 URIs and the HTTPS output URLs returned by HealthScribe."""
    parsed = urlparse(uri)
    if parsed.scheme == "s3":
        bucket_and_key = parsed.path.lstrip("/").split("/", 1)
        bucket = parsed.netloc
    elif parsed.scheme == "https":
        path_parts = parsed.path.lstrip("/").split("/", 1)
        # Virtual-hosted style: https://bucket.s3.region.amazonaws.com/key
        if ".s3." in parsed.netloc or ".s3-" in parsed.netloc:
            bucket = parsed.netloc.split(".s3", 1)[0]
            bucket_and_key = path_parts
        # Path style: https://s3.region.amazonaws.com/bucket/key
        else:
            bucket_and_key = path_parts
            bucket = bucket_and_key.pop(0) if bucket_and_key else ""
    else:
        raise ValueError("HealthScribe returned an invalid output location.")
    if not bucket or not bucket_and_key or not bucket_and_key[0]:
        raise ValueError("HealthScribe returned an invalid S3 output location.")
    return bucket, unquote(bucket_and_key[0])


def segments_from_healthscribe(document: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for segment in document.get("Conversation", {}).get("TranscriptSegments", []):
        text = str(segment.get("Content", "")).strip()
        if not text:
            continue
        role = segment.get("ParticipantDetails", {}).get("ParticipantRole")
        result.append({
            "start": float(segment.get("BeginAudioTime", 0)),
            "end": float(segment.get("EndAudioTime", 0)),
            "text": text,
            **({"speaker": role} if role else {}),
        })
    return result


def summary_from_healthscribe(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": str(section.get("SectionName", "Clinical note")).replace("_", " ").title(),
            "items": [item["SummarizedSegment"] for item in section.get("Summary", []) if item.get("SummarizedSegment")],
        }
        for section in document.get("ClinicalDocumentation", {}).get("Sections", [])
        if section.get("Summary")
    ]


def process_job(session_id: str, job_name: str, input_key: str, storage: dict | None = None) -> None:
    """Download completed HealthScribe JSON files to the local session folder."""
    directory = session_directory(session_id)
    try:
        input_bucket = storage['bucket'] if storage else configuration()[0]
        region = storage['region'] if storage else AWS_REGION
        transcribe = boto3.client("transcribe", region_name=region)
        s3 = boto3.client("s3", region_name=region)
        while True:
            job = transcribe.get_medical_scribe_job(MedicalScribeJobName=job_name)["MedicalScribeJob"]
            state = job["MedicalScribeJobStatus"]
            if state in {"COMPLETED", "FAILED"}:
                break
            write_json(status_path(session_id), {"id": session_id, "status": state, "job_name": job_name})
            time.sleep(POLL_SECONDS)
        if state == "FAILED":
            raise RuntimeError(job.get("FailureReason", "HealthScribe did not complete the job."))

        outputs = job["MedicalScribeOutput"]
        transcript_bucket, transcript_key = s3_location(outputs["TranscriptFileUri"])
        note_bucket, note_key = s3_location(outputs["ClinicalDocumentUri"])
        if storage and (transcript_bucket != storage['bucket'] or note_bucket != storage['bucket']):
            raise RuntimeError("HealthScribe results are outside the organization bucket.")
        raw_transcript = json.loads(s3.get_object(Bucket=transcript_bucket, Key=transcript_key)["Body"].read())
        raw_note = json.loads(s3.get_object(Bucket=note_bucket, Key=note_key)["Body"].read())
        write_json(directory / "healthscribe-transcript.json", raw_transcript)
        write_json(directory / "clinical-note.json", raw_note)
        segments = segments_from_healthscribe(raw_transcript)
        recording = next(directory.glob("recording.*"))
        clinical_note = summary_from_healthscribe(raw_note)
        write_json(transcript_path(session_id), {
            "id": session_id,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "audio": {"file": recording.name, "mime_type": AUDIO_MIME_TYPES.get(recording.suffix.lower(), "application/octet-stream")},
            "speakers": {},
            "text": " ".join(segment["text"] for segment in segments),
            "segments": segments,
            "clinical_note": clinical_note,
            "healthscribe": {
                "job_name": job_name,
                "input_uri": f"s3://{input_bucket}/{input_key}",
                "transcript_uri": outputs["TranscriptFileUri"],
                "clinical_note_uri": outputs["ClinicalDocumentUri"],
            },
        })
        if storage:
            organization_storage.publish_results(storage, directory, segments, clinical_note, raw_transcript, raw_note)
        write_json(status_path(session_id), {"id": session_id, "status": "COMPLETED", "job_name": job_name})
    except (BotoCoreError, ClientError, KeyError, OSError, ValueError, RuntimeError, PsycopgError) as exc:
        write_json(status_path(session_id), {"id": session_id, "status": "FAILED", "job_name": job_name, "detail": str(exc)})
        if storage:
            organization_storage.set_job_status(storage, 'FAILED', 'Session processing failed. Please contact support before retrying.')


@app.get("/")
def page():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/recordings/{session_id}/{filename}")
def session_recording(session_id: str, filename: str, request: Request = None):
    job = getattr(request.state, 'storage_job', None) if request else None
    if job:
        try:
            organization_storage.restore_artifact(job['storage'], filename, session_directory(session_id))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Recording not found.") from exc
    path = session_directory(session_id) / Path(filename).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Recording not found.")
    return FileResponse(path, media_type=AUDIO_MIME_TYPES.get(path.suffix.lower(), "application/octet-stream"), filename=path.name)


@app.get("/transcripts")
def transcripts(request: Request = None):
    if request and os.getenv('ORGANIZATION_STORAGE_ENABLED') == 'true':
        return organization_storage.completed_jobs(request.state.care_context)
    items = []
    for path in RECORDINGS_DIRECTORY.glob("*/transcript.json") if RECORDINGS_DIRECTORY.exists() else []:
        if re.fullmatch(r"session-[0-9a-f-]{36}", path.parent.name):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append({"id": path.parent.name, "label": path.parent.name, "text": data.get("text", ""), "created_at": data.get("created_at", "")})
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(items, key=lambda item: item["created_at"], reverse=True)


@app.get("/transcripts/{session_id}")
def transcript(session_id: str, request: Request = None):
    job = getattr(request.state, 'storage_job', None) if request else None
    if job:
        data = organization_storage.session_review.read_result(job['storage'])
        if not data:
            raise HTTPException(status_code=404, detail="Transcript not found.")
        return data
    if os.getenv('ORGANIZATION_STORAGE_ENABLED') == 'true':
        raise HTTPException(status_code=404, detail="Transcript not found.")
    path = transcript_path(session_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Transcript not found.")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["recording_url"] = f"/recordings/{session_id}/{data['audio']['file']}"
    return data


@app.get("/transcripts/{session_id}/status")
def job_status(session_id: str, request: Request = None):
    job = getattr(request.state, 'storage_job', None) if request else None
    if job:
        return {'id': session_id, 'status': job['status'], 'detail': job['detail']}
    if os.getenv('ORGANIZATION_STORAGE_ENABLED') == 'true':
        raise HTTPException(status_code=404, detail="Processing status not found.")
    path = status_path(session_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Processing status not found.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.put("/transcripts/{session_id}/speakers")
def save_speaker_labels(session_id: str, labels: dict[str, str] = Body(...), request: Request = None):
    job = getattr(request.state, 'storage_job', None) if request else None
    if job:
        actor = validate_access_token(request.headers.get('authorization'))
        try:
            speakers = organization_storage.session_review.save_speaker_labels(job['storage'], labels, actor['sub'])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if speakers is None:
            raise HTTPException(status_code=404, detail="Transcript not found.")
        return {'speakers': speakers}
    if os.getenv('ORGANIZATION_STORAGE_ENABLED') == 'true':
        raise HTTPException(status_code=404, detail="Transcript not found.")
    path = transcript_path(session_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Transcript not found.")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["speakers"] = {key.strip(): value.strip() for key, value in labels.items() if key.strip() and value.strip()}
    write_json(path, data)
    return {"speakers": data["speakers"]}


@app.post("/transcribe", status_code=202)
async def transcribe(background_tasks: BackgroundTasks, audio: UploadFile = File(...), request: Request = None):
    suffix = Path(audio.filename or "recording.webm").suffix.lower()
    if suffix not in AUDIO_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Choose a WAV, MP3, M4A, MP4, FLAC, Ogg, WebM, or AMR audio file.")
    if audio.size is not None and audio.size > MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio files must be 100 MB or smaller.")
    content = await audio.read(MAX_AUDIO_UPLOAD_BYTES + 1)
    if len(content) > MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio files must be 100 MB or smaller.")
    if not content:
        raise HTTPException(status_code=400, detail="The audio file is empty.")
    storage = None
    try:
        if request is not None and os.getenv('ORGANIZATION_STORAGE_ENABLED') == 'true':
            actor = validate_access_token(request.headers.get('authorization'))
            storage = organization_storage.create_upload(request.state.care_context, suffix, actor['sub'])
            input_bucket = output_bucket = storage['bucket']
            data_role = storage['healthscribe_role_arn']
        else:
            input_bucket, output_bucket, data_role = configuration()
    except (RuntimeError, PsycopgError) as exc:
        raise HTTPException(status_code=503, detail="Organization storage is unavailable.") from exc
    session_id = storage['runtime_id'] if storage else f"session-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    job_name = storage['job_name'] if storage else f"healthscribe-{datetime.now():%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
    directory = session_directory(session_id)
    input_key = storage['audio_key'] if storage else f"recordings/{session_id}/recording{suffix}"
    try:
        directory.mkdir(parents=True)
        recording = directory / f"recording{suffix}"
        recording.write_bytes(content)
        if storage:
            organization_storage.put_artifact(storage, recording, 'audio_recording', input_key, AUDIO_MIME_TYPES[suffix], 'user_upload')
        else:
            boto3.client("s3", region_name=AWS_REGION).upload_file(str(recording), input_bucket, input_key)
        encryption = {'OutputEncryptionKMSKeyId': storage['kms_key_arn']} if storage else {}
        boto3.client("transcribe", region_name=storage['region'] if storage else AWS_REGION).start_medical_scribe_job(
            MedicalScribeJobName=job_name,
            Media={"MediaFileUri": f"s3://{input_bucket}/{input_key}"},
            OutputBucketName=output_bucket,
            DataAccessRoleArn=data_role,
            Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": HEALTHSCRIBE_MAX_SPEAKERS},
            **encryption,
        )
        if storage:
            organization_storage.set_job_status(storage, 'IN_PROGRESS')
        write_json(status_path(session_id), {"id": session_id, "status": "IN_PROGRESS", "job_name": job_name})
        if storage:
            background_tasks.add_task(process_job, session_id, job_name, input_key, storage)
        else:
            background_tasks.add_task(process_job, session_id, job_name, input_key)
        return {"id": session_id, "status": "IN_PROGRESS"}
    except (BotoCoreError, ClientError, OSError, PsycopgError) as exc:
        if storage:
            organization_storage.set_job_status(storage, 'FAILED', 'Audio upload or job submission failed.')
        raise HTTPException(status_code=500, detail="Could not start the audio processing job.") from exc

