"""Local recorder server backed by Amazon HealthScribe batch jobs."""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urlparse
from uuid import uuid4

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
from database.longitudinal_records import InsightEvidence, InsightItem, LongitudinalRecordRepository
from ai_harness.brief_projection import project_accepted_insights
from pydantic import BaseModel, Field, field_validator

app = FastAPI()
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


class TherapistOnboardingRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=200)
    professional_name: str = Field(min_length=1, max_length=200)
    practice_type: Literal["solo", "group"]
    team_setup: Literal["later", "now"]


class ClientPortalPermissionsRequest(BaseModel):
    organization_id: str = Field(min_length=1, max_length=64)
    client_id: str = Field(min_length=1, max_length=64)
    can_view_session_history: bool
    can_view_shared_transcripts: bool
    can_view_insights: bool
    can_view_draft_notes: bool
    can_view_approved_summaries: bool = False
    can_play_shared_recordings: bool = False


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
            LIMIT 1
        """, (claims["sub"], claims["sub"]))
        identity = cursor.fetchone()
    if not identity:
        raise HTTPException(status_code=403, detail="Your authenticated account is not connected to this workspace.")
    return {"role": identity["role"], "displayName": identity["display_name"] or "there"}


PERMISSION_FIELDS = ("can_view_session_history", "can_view_shared_transcripts", "can_view_insights", "can_view_draft_notes", "can_play_shared_recordings")


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
                client.display_name AS name, client.email, client.phone, client.status
            FROM app.clients client
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
    return {"clients": [{**row, "id": str(row["id"]), "organization_id": str(row["organization_id"])} for row in rows]}


def read_portal_permissions(connection, context):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {', '.join(PERMISSION_FIELDS)} FROM app.client_portal_permissions WHERE organization_id=%s AND client_id=%s", (context["organization_id"], context["client_id"]))
        row = cursor.fetchone()
    return {key: bool(row and row[key]) for key in PERMISSION_FIELDS}


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
                WHERE portal.auth0_subject=%s AND portal.status='active' AND client.status='active'
                AND portal.synthetic_case_key='heartwell-sadic'""", (claims["sub"],))
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise HTTPException(status_code=403, detail="No active linked client context is available.")
    return {key: str(value) for key, value in rows[0].items()}


class AccountProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    about_me: str | None = Field(default=None, max_length=2000)

    @field_validator("name", "email", "phone", "about_me")
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
    identity = current_identity(authorization)
    role = identity["role"]
    with connection.cursor() as cursor:
        if role == "therapist":
            cursor.execute("""SELECT DISTINCT practitioner.id, practitioner.professional_name AS name,
                practitioner.contact_email AS email, practitioner.contact_phone AS phone
                FROM app.application_users actor
                JOIN app.organization_memberships membership ON membership.user_id=actor.id
                JOIN app.organization_practitioners practitioner ON practitioner.membership_id=membership.id
                WHERE actor.auth0_subject=%s AND actor.status='active'
                  AND membership.status='active' AND membership.starts_at<=CURRENT_TIMESTAMP
                  AND (membership.ends_at IS NULL OR membership.ends_at>CURRENT_TIMESTAMP)
                  AND practitioner.status='active'""", (claims["sub"],))
        else:
            cursor.execute("""SELECT client.id, client.display_name AS name, client.email, client.phone
                FROM app.client_portal_accounts portal JOIN app.clients client ON client.id=portal.client_id
                WHERE portal.auth0_subject=%s AND portal.status='active' AND client.status='active'""",
                (claims["sub"],))
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise HTTPException(status_code=403, detail="An unambiguous active account profile is not available.")
    return role, claims["sub"], rows[0]


@app.get("/account/profile")
def get_account_profile(authorization: str | None = Header(default=None)):
    with connect() as connection:
        role, subject, target = account_profile_target(connection, authorization)
        with connection.cursor() as cursor:
            cursor.execute("SELECT about_me, photo IS NOT NULL AS has_photo FROM app.account_profiles WHERE auth0_subject=%s", (subject,))
            extras = cursor.fetchone() or {}
    return {"role": role, "name": target["name"] or "", "email": target["email"],
            "phone": target["phone"], "aboutMe": extras.get("about_me") if role == "therapist" else None,
            "photoUrl": "/api/account/profile/photo" if extras.get("has_photo") else None}


@app.put("/account/profile")
def update_account_profile(request: AccountProfileUpdate, authorization: str | None = Header(default=None)):
    with connect() as connection:
        role, subject, target = account_profile_target(connection, authorization)
        if role == "client" and request.about_me is not None:
            raise HTTPException(status_code=403, detail="About me is not enabled for client accounts.")
        with connection.cursor() as cursor:
            if role == "therapist":
                cursor.execute("""UPDATE app.organization_practitioners
                    SET professional_name=%s, contact_email=%s, contact_phone=%s
                    WHERE id=%s""", (request.name, request.email, request.phone, target["id"]))
            else:
                cursor.execute("UPDATE app.clients SET display_name=%s, email=%s, phone=%s WHERE id=%s",
                    (request.name, request.email, request.phone, target["id"]))
                cursor.execute("UPDATE app.client_portal_accounts SET display_name=%s WHERE client_id=%s",
                    (request.name, target["id"]))
            if role == "therapist":
                cursor.execute("""INSERT INTO app.account_profiles (auth0_subject, about_me) VALUES (%s,%s)
                    ON CONFLICT (auth0_subject) DO UPDATE SET about_me=EXCLUDED.about_me""",
                    (subject, request.about_me))
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
def relationship_photo(authorization: str | None = Header(default=None)):
    identity = current_identity(authorization)
    therapist = identity["role"] == "therapist"
    with connect() as connection:
        context = resolve_sharing_context(connection, authorization, therapist=therapist)
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
        context = resolve_sharing_context(connection, authorization, therapist=therapist)
        # Existing session and insight APIs are bound to the linked demo case.
        # Never render that workspace under a different client's URL.
        if client_id is not None and (not therapist or client_id != context["client_id"]):
            raise HTTPException(status_code=403, detail="This client workspace is not available for your account.")
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
            "imageSrc": "/api/relationship-profile/photo" if extras.get("has_photo") else None,
            "aboutMe": extras.get("about_me") if not therapist else None}
    if therapist:
        profile.update(organizationId=context["organization_id"], clientId=context["client_id"],
                       syntheticCase=row.get("synthetic_case_key") == "heartwell-sadic")
    return profile


@app.get("/client-portal-permissions")
def get_client_portal_permissions(authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = resolve_sharing_context(connection, authorization, therapist=True)
        return {**context, **read_portal_permissions(connection, context)}


@app.put("/client-portal-permissions")
def update_client_portal_permissions(request: ClientPortalPermissionsRequest, authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = resolve_sharing_context(connection, authorization, therapist=True, write=True)
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
        return {**context, **row}


def shared_session_materials(context, permissions):
    # Explicit allowlist: never include arbitrary runtime recordings or provider metadata.
    materials = []
    for job in organization_storage.completed_job_records(context):
        data = organization_storage.session_review.read_result(job["storage"])
        if not data:
            continue
        session_id = job["runtime_id"]
        item = {"id": session_id, "label": job["label"]}
        if permissions["can_view_session_history"]:
            item["created_at"] = job["created_at"].isoformat()
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
        result = {"permissions": permissions}
        if any(permissions[key] for key in ("can_view_session_history", "can_view_shared_transcripts", "can_view_draft_notes")):
            result["sessions"] = shared_session_materials(context, permissions)
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
                context = resolve_sharing_context(connection, request.headers.get("authorization"), therapist=True, write=request.method not in ("GET", "HEAD"))
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
    """Return only accepted insight items for a bounded future brief packet."""
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
    return project_accepted_insights(packet, journey)


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
            Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2},
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

