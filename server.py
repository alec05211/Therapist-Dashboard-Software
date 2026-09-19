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
from database.longitudinal_records import InsightEvidence, InsightItem, LongitudinalRecordRepository
from ai_harness.pre_session import build_pre_session_synthesis_request, generate_openai_pre_session_brief
from pydantic import BaseModel, Field, field_validator

app = FastAPI()
# Kept explicit so Uvicorn's local reload watcher reloads the application
# boundary when authentication behavior changes during development.
load_dotenv(Path(__file__).with_name(".env"))
RECORDINGS_DIRECTORY = Path(__file__).with_name("recordings")
DEMO_DATA_DIRECTORY = Path(__file__).with_name("demo-data")
DEMO_SESSION_ONE_RELATIVE_DIRECTORY = Path("demo-data") / "heartwell-sadic-case" / "session-01-intake-and-stabilization"
DEMO_SESSION_ONE_DIRECTORY = Path(__file__).parent / DEMO_SESSION_ONE_RELATIVE_DIRECTORY
DEMO_SESSION_ONE_RECORDING = DEMO_SESSION_ONE_DIRECTORY / "recording.wav"
DEMO_SESSION_ONE_STATUS = DEMO_SESSION_ONE_DIRECTORY / "healthscribe-status.json"
DEMO_SESSION_ONE_ID = "heartwell-sadic-session-01"
DEMO_SESSION_ONE_TRANSCRIPT = DEMO_SESSION_ONE_DIRECTORY / "transcript.json"
DEMO_SESSION_TWO_RELATIVE_DIRECTORY = Path("demo-data") / "heartwell-sadic-case" / "session-02-noticing-the-pressure-cycle"
DEMO_SESSION_TWO_DIRECTORY = Path(__file__).parent / DEMO_SESSION_TWO_RELATIVE_DIRECTORY
DEMO_SESSION_TWO_RECORDING = DEMO_SESSION_TWO_DIRECTORY / "recording.wav"
DEMO_SESSION_TWO_STATUS = DEMO_SESSION_TWO_DIRECTORY / "healthscribe-status.json"
DEMO_SESSION_TWO_ID = "heartwell-sadic-session-02"
DEMO_SESSION_TWO_TRANSCRIPT = DEMO_SESSION_TWO_DIRECTORY / "transcript.json"
DEMO_SESSION_SLUGS = {
    3: "making-room-for-rest",
    4: "the-deadline-setback",
    5: "practicing-clear-requests",
    6: "six-session-review",
}
DEMO_SESSION_LABELS = {
    1: "Synthetic · Elena Sadić · Session 01",
    2: "Synthetic · Elena Sadić · Session 02",
    3: "Synthetic · Elena Sadić · Session 03",
    4: "Synthetic · Elena Sadić · Session 04",
    5: "Synthetic · Elena Sadić · Session 05",
    6: "Synthetic · Elena Sadić · Session 06",
}
MAX_DEMO_AUDIO_BYTES = 100 * 1024 * 1024
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
                cursor.execute("""SELECT client.display_name AS name, client.email, client.phone, portal.auth0_subject
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
    return {"name": name, "role": role, "initials": "".join(part[0] for part in name.split()[:2]).upper(),
            "email": row["email"], "phone": row["phone"],
            "imageSrc": "/api/relationship-profile/photo" if extras.get("has_photo") else None,
            "aboutMe": extras.get("about_me") if not therapist else None}


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


def shared_session_materials(permissions):
    # Explicit allowlist: never include arbitrary runtime recordings or provider metadata.
    materials = []
    for number in range(1, 7):
        session_id = f"heartwell-sadic-session-{number:02d}"
        assets = demo_session_assets(session_id)
        if not assets or not assets[2].is_file():
            continue
        data = json.loads(assets[2].read_text(encoding="utf-8"))
        item = {"id": session_id, "label": DEMO_SESSION_LABELS[number]}
        if permissions["can_view_session_history"]:
            item["created_at"] = data.get("created_at", "")
        if permissions["can_view_shared_transcripts"]:
            item["segments"] = [{"speaker": data.get("speakers", {}).get(segment.get("speaker"), segment.get("speaker", "")), "text": segment.get("text", ""), "start": segment.get("start", 0), "end": segment.get("end", 0)} for segment in data.get("segments", [])]
        if permissions["can_play_shared_recordings"] and permissions["can_view_shared_transcripts"] and assets[0].is_file():
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
            result["sessions"] = shared_session_materials(permissions)
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
    allowed = {f"heartwell-sadic-session-{number:02d}" for number in range(1, 7)}
    if session_id not in allowed:
        raise HTTPException(status_code=404, detail="Shared recording not found.")
    assets = demo_session_assets(session_id)
    if not assets or not assets[0].is_file():
        raise HTTPException(status_code=404, detail="Shared recording not found.")
    return FileResponse(assets[0], media_type="audio/wav", filename=f"{session_id}.wav", headers={"Cache-Control": "no-store"})


@app.middleware("http")
async def protect_legacy_clinical_routes(request: Request, call_next):
    # The old filesystem API is therapist-only, including direct backend requests.
    path = request.url.path
    if path.startswith(("/transcripts", "/recordings", "/demo/")) or path == "/transcribe":
        try:
            with connect() as connection:
                resolve_sharing_context(connection, request.headers.get("authorization"), therapist=True, write=request.method not in ("GET", "HEAD"))
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


def is_demo_session_one(session_id: str) -> bool:
    return session_id == DEMO_SESSION_ONE_ID


def is_demo_session_two(session_id: str) -> bool:
    return session_id == DEMO_SESSION_TWO_ID


def demo_session_assets(session_id: str) -> tuple[Path, Path, Path] | None:
    if is_demo_session_one(session_id):
        return DEMO_SESSION_ONE_RECORDING, DEMO_SESSION_ONE_STATUS, DEMO_SESSION_ONE_TRANSCRIPT
    if is_demo_session_two(session_id):
        return DEMO_SESSION_TWO_RECORDING, DEMO_SESSION_TWO_STATUS, DEMO_SESSION_TWO_TRANSCRIPT
    session_number = additional_demo_session_number(session_id)
    if session_number is not None:
        recording, job_status, transcript, _, _ = additional_demo_session_assets(session_number)
        return recording, job_status, transcript
    return None


def additional_demo_session_assets(session_number: int) -> tuple[Path, Path, Path, str, str]:
    """Return the data-closet paths and UI metadata for Sessions 03 through 06."""
    slug = DEMO_SESSION_SLUGS.get(session_number)
    label = DEMO_SESSION_LABELS.get(session_number)
    if not slug or not label:
        raise HTTPException(status_code=404, detail="Unknown synthetic demo session.")
    directory = DEMO_DATA_DIRECTORY / "heartwell-sadic-case" / f"session-{session_number:02d}-{slug}"
    return (
        directory / "recording.wav",
        directory / "healthscribe-status.json",
        directory / "transcript.json",
        f"heartwell-sadic-session-{session_number:02d}",
        label,
    )


def additional_demo_session_number(session_id: str) -> int | None:
    for session_number in DEMO_SESSION_SLUGS:
        if session_id == f"heartwell-sadic-session-{session_number:02d}":
            return session_number
    return None


def demo_session_number(session_id: str) -> int | None:
    """Return a synthetic session number for any session in the Heartwell case."""
    try:
        number = int(session_id.rsplit("-", maxsplit=1)[-1])
    except ValueError:
        return None
    return number if number in DEMO_SESSION_LABELS else None


def demo_brief_evidence(session_id: str, segment_text: str) -> dict[str, Any]:
    """Resolve a deliberately selected synthetic-demo citation to a transcript segment.

    This is the first deterministic evidence-retrieval seam for the harness demo.
    It does not infer clinical meaning or call a model; production retrieval will
    replace the selected text with versioned, authorized memory-item sources.
    """
    assets = demo_session_assets(session_id)
    if assets is None:
        raise HTTPException(status_code=404, detail="Unknown synthetic demo session.")
    transcript = json.loads(assets[2].read_text(encoding="utf-8"))
    for index, segment in enumerate(transcript.get("segments", [])):
        if segment.get("text", "").strip() == segment_text:
            return {
                "evidence_id": f"{session_id}:segment:{index}",
                "session_id": session_id,
                "session_label": DEMO_SESSION_LABELS.get(demo_session_number(session_id) or 0, "Synthetic · Elena Sadić"),
                "segment_index": index,
                "start": segment["start"],
                "end": segment["end"],
                "quote": segment["text"].strip(),
            }
    raise RuntimeError(f"Synthetic demo evidence was not found for {session_id}.")


def demo_longitudinal_insights() -> dict[str, Any]:
    """Return the evidence-led longitudinal workspace for the synthetic case.

    This is deliberately an application-owned projection, not a model's hidden
    memory. Every insight is a clinician-review prompt with transcript evidence;
    the accompanying HealthScribe notes are marked generated until a therapist
    revision workflow exists.
    """
    session_one = "heartwell-sadic-session-01"
    session_two = "heartwell-sadic-session-02"
    session_four = "heartwell-sadic-session-04"
    session_five = "heartwell-sadic-session-05"
    session_six = "heartwell-sadic-session-06"
    evidence = {
        "pressure_origin": demo_brief_evidence(session_one, "Lately, it feels like I am either working, thinking about working, or feeling guilty that I am not working."),
        "role_history": demo_brief_evidence(session_one, "My family relied on me a lot when my dad got sick last year."),
        "rest_rule": demo_brief_evidence(session_two, "Like if I'm not hard on myself, I will become careless."),
        "setback": demo_brief_evidence(session_four, "I did not ask which case had priority."),
        "request": demo_brief_evidence(session_five, "My heart was racing before I spoke, but I said, I can move both cases forward, and I need help deciding which one takes precedence today."),
        "help_as_debt": demo_brief_evidence(session_five, "Someone helps me and then I feel like I have to repay them right away."),
        "current_shift": demo_brief_evidence(session_six, "Sometimes I catch it."),
        "launch": demo_brief_evidence(session_six, "I need to ask for priorities before I'm already overwhelmed."),
        "care": demo_brief_evidence(session_six, "I still do not know how to let people take care of me without feeling like I owe them something."),
        "father": demo_brief_evidence(session_six, "And I want to talk more about my dad because I think a lot of this started before my job got so busy."),
    }
    records = [
        {"session_id": f"heartwell-sadic-session-{number:02d}", "session_label": DEMO_SESSION_LABELS[number], "note_status": "Generated HealthScribe note — not therapist-finalized", "included": True}
        for number in range(1, 7)
    ]
    patterns = [
        {
            "id": "pressure-cycle",
            "title": "Pressure, self-criticism, and overextension",
            "summary": "Possible pattern to review: pressure and anticipated disappointment have repeatedly been followed by overwork, reduced rest, and difficulty asking for priorities. The latest session includes an earlier recognition of that sequence.",
            "evidence": [evidence["pressure_origin"], evidence["setback"], evidence["current_shift"]],
            "status": "Review prompt · supported across 3 sessions",
        },
        {
            "id": "direct-requests",
            "title": "Direct requests as a developing practice",
            "summary": "Across recent sessions, direct requests to a supervisor and close supports appear to be a meaningful area of practice. This is not presented as a treatment conclusion; it is a source-grounded thread for therapist review.",
            "evidence": [evidence["setback"], evidence["request"], evidence["launch"]],
            "status": "Review prompt · supported across 3 sessions",
        },
        {
            "id": "care-and-obligation",
            "title": "Care, obligation, and family context",
            "summary": "The record links early responsibility during the father's illness with a current difficulty accepting help without feeling indebted. This connection remains exploratory and should be held as a question, not a fact about the client.",
            "evidence": [evidence["role_history"], evidence["help_as_debt"], evidence["care"]],
            "status": "Review prompt · supported across 3 sessions",
        },
    ]
    open_threads = [
        {"text": "What feels important to understand about receiving care without turning it into obligation?", "evidence": [evidence["care"], evidence["help_as_debt"]]},
        {"text": "What connection, if any, does the client want to explore between current pressure and the experience of the father's illness?", "evidence": [evidence["father"], evidence["role_history"]]},
        {"text": "How is the approaching launch affecting the client's ability to use the priority question before pressure escalates?", "evidence": [evidence["launch"], evidence["request"]]},
    ]
    packet_items = [
        {"kind": "last-session context", "text": "The upcoming launch and the client's own priority question.", "evidence": [evidence["launch"]]},
        {"kind": "longitudinal review prompt", "text": "Pressure, self-criticism, and overextension across Sessions 01, 04, and 06.", "evidence": [evidence["pressure_origin"], evidence["setback"], evidence["current_shift"]]},
        {"kind": "longitudinal review prompt", "text": "Direct requests across work and close relationships.", "evidence": [evidence["setback"], evidence["request"]]},
        {"kind": "open thread", "text": "Care and obligation.", "evidence": [evidence["care"], evidence["help_as_debt"]]},
        {"kind": "open thread", "text": "Family context and the father's illness.", "evidence": [evidence["father"], evidence["role_history"]]},
    ]
    return {
        "status": "SYNTHETIC REVIEW WORKSPACE · updated after Session 06",
        "review_note": "This workspace is a clinician-review aid. It does not diagnose, determine risk, or make treatment decisions.",
        "records": records,
        "narrative": "Across six sessions, the record describes a recurring pressure cycle involving anticipated disappointment, increased self-demand, and less room for rest or support. Recent sessions also show the client practicing more direct requests and sometimes recognizing the cycle earlier. The links between responsibility, care, and family experience remain important but unresolved.",
        "patterns": patterns,
        "open_threads": open_threads,
        "context_packet": {
            "purpose": "Bounded source packet for the next pre-session brief.",
            "selection_policy": "Latest session context, cross-session review prompts, and explicit open threads; generated notes do not override therapist-finalized records.",
            "items": packet_items,
            "approved_evidence": list(evidence.values()),
            "records": records,
        },
    }


@app.get("/demo/heartwell-sadic/pre-session-brief")
def demo_pre_session_brief():
    """Return a cited, deterministic pre-session brief for synthetic demo data only.

    This proves the harness contract—bounded sections, selected evidence, and
    citations—without sending data to an external model or making clinical
    inferences. It is not a production clinical brief generator.
    """
    session_id = "heartwell-sadic-session-06"
    return {
        "status": "DEMO DRAFT · deterministic evidence selection",
        "review_note": "Review the cited source before relying on any item. This demo does not assess diagnosis, risk, or treatment.",
        "sections": [
            {
                "title": "Since last session",
                "items": [{
                    "text": "an approaching project launch and the vulnerability of asking for priorities before feeling overwhelmed.",
                    "sources": [demo_brief_evidence(session_id, "I need to ask for priorities before I'm already overwhelmed.")],
                }],
            },
            {
                "title": "Important trajectory",
                "items": [{
                    "text": "the client noticing the familiar pressure sequence sooner and sometimes interrupting it.",
                    "sources": [demo_brief_evidence(session_id, "Sometimes I catch it.")],
                }],
            },
            {
                "title": "Open loops",
                "items": [
                    {
                        "text": "how to receive care without feeling indebted.",
                        "sources": [demo_brief_evidence(session_id, "I still do not know how to let people take care of me without feeling like I owe them something.")],
                    },
                    {
                        "text": "what may still need to be understood about the relationship with their father.",
                        "sources": [demo_brief_evidence(session_id, "And I want to talk more about my dad because I think a lot of this started before my job got so busy.")],
                    },
                ],
            },
        ],
    }


@app.get("/demo/heartwell-sadic/pre-session-brief/request")
def demo_pre_session_synthesis_request():
    """Expose the model-ready synthetic bundle without contacting a provider."""
    insights = demo_longitudinal_insights()
    return build_pre_session_synthesis_request(
        client_reference="synthetic-heartwell-sadic-client",
        evidence=insights["context_packet"]["approved_evidence"],
        context_packet=insights["context_packet"],
    )


@app.get("/demo/heartwell-sadic/insights")
def demo_client_insights():
    """Return the synthetic, evidence-led clinical-insights workspace."""
    return demo_longitudinal_insights()


@app.post("/demo/heartwell-sadic/pre-session-brief/generate")
def generate_demo_pre_session_brief():
    """Generate a synthetic-only, cited draft through the configured OpenAI key."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="OPENAI_API_KEY is not configured.")
    insights = demo_longitudinal_insights()
    evidence = insights["context_packet"]["approved_evidence"]
    synthesis_request = build_pre_session_synthesis_request(
        client_reference="synthetic-heartwell-sadic-client",
        evidence=evidence,
        context_packet=insights["context_packet"],
    )
    try:
        generated, metadata = generate_openai_pre_session_brief(
            synthesis_request=synthesis_request,
            api_key=api_key,
            model=os.getenv("OPENAI_PRE_SESSION_MODEL", "gpt-5-mini"),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    sources_by_id = {source["evidence_id"]: source for source in evidence}
    return {
        "status": f"OPENAI DRAFT · {metadata['model']}",
        "review_note": "Synthetic demo only. Review cited sources before relying on an item; this draft does not assess diagnosis, risk, or treatment.",
        "sections": [
            {
                "title": section["title"],
                "items": [
                    {"text": item["text"], "sources": [sources_by_id[evidence_id] for evidence_id in item["evidence_ids"]]}
                    for item in section["items"]
                ],
            }
            for section in generated["sections"]
        ],
        "generation": metadata,
    }


def write_json(path: Path, content: dict[str, Any]) -> None:
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")


@app.post("/demo/heartwell-sadic/session-01/audio", status_code=status.HTTP_201_CREATED)
async def upload_demo_session_one_audio(audio: UploadFile = File(...)):
    """Store one explicitly synthetic WAV file in the versioned demo-data closet.

    This intentionally does not start a HealthScribe job or write to the normal
    runtime recordings directory. It exists solely to stage Elena and Jeremy's
    first synthetic session before it is submitted through the normal pipeline.
    """
    filename = audio.filename or ""
    if Path(filename).suffix.lower() != ".wav":
        raise HTTPException(status_code=415, detail="The session-one demo upload must be a WAV file.")
    if DEMO_SESSION_ONE_RECORDING.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session-one demo recording already exists. Remove it deliberately before replacing it.",
        )

    contents = await audio.read(MAX_DEMO_AUDIO_BYTES + 1)
    if len(contents) > MAX_DEMO_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="The demo recording exceeds the 100 MB limit.")
    if len(contents) < 12 or contents[:4] != b"RIFF" or contents[8:12] != b"WAVE":
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid WAV container.")

    try:
        DEMO_SESSION_ONE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        DEMO_SESSION_ONE_RECORDING.write_bytes(contents)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not store the demo recording.") from exc

    return {
        "stored": True,
        "session": "heartwell-sadic/session-01",
        "path": str(DEMO_SESSION_ONE_RELATIVE_DIRECTORY / "recording.wav"),
        "bytes": len(contents),
    }


def process_demo_session_one_job(job_name: str, input_key: str) -> None:
    """Persist HealthScribe artifacts beside the explicitly synthetic source WAV."""
    try:
        input_bucket, _, _ = configuration()
        transcribe = boto3.client("transcribe", region_name=AWS_REGION)
        s3 = boto3.client("s3", region_name=AWS_REGION)
        while True:
            job = transcribe.get_medical_scribe_job(MedicalScribeJobName=job_name)["MedicalScribeJob"]
            state = job["MedicalScribeJobStatus"]
            if state in {"COMPLETED", "FAILED"}:
                break
            write_json(DEMO_SESSION_ONE_STATUS, {"id": DEMO_SESSION_ONE_ID, "status": state, "job_name": job_name})
            time.sleep(POLL_SECONDS)
        if state == "FAILED":
            raise RuntimeError(job.get("FailureReason", "HealthScribe did not complete the job."))

        outputs = job["MedicalScribeOutput"]
        transcript_bucket, transcript_key = s3_location(outputs["TranscriptFileUri"])
        note_bucket, note_key = s3_location(outputs["ClinicalDocumentUri"])
        raw_transcript = json.loads(s3.get_object(Bucket=transcript_bucket, Key=transcript_key)["Body"].read())
        raw_note = json.loads(s3.get_object(Bucket=note_bucket, Key=note_key)["Body"].read())
        write_json(DEMO_SESSION_ONE_DIRECTORY / "healthscribe-transcript.json", raw_transcript)
        write_json(DEMO_SESSION_ONE_DIRECTORY / "clinical-note.json", raw_note)
        segments = segments_from_healthscribe(raw_transcript)
        write_json(DEMO_SESSION_ONE_DIRECTORY / "transcript.json", {
            "id": DEMO_SESSION_ONE_ID,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "audio": {"file": DEMO_SESSION_ONE_RECORDING.name, "mime_type": "audio/wav"},
            "speakers": {},
            "text": " ".join(segment["text"] for segment in segments),
            "segments": segments,
            "clinical_note": summary_from_healthscribe(raw_note),
            "healthscribe": {
                "job_name": job_name,
                "input_uri": f"s3://{input_bucket}/{input_key}",
                "transcript_uri": outputs["TranscriptFileUri"],
                "clinical_note_uri": outputs["ClinicalDocumentUri"],
            },
        })
        write_json(DEMO_SESSION_ONE_STATUS, {"id": DEMO_SESSION_ONE_ID, "status": "COMPLETED", "job_name": job_name})
    except (BotoCoreError, ClientError, KeyError, OSError, ValueError, RuntimeError) as exc:
        write_json(DEMO_SESSION_ONE_STATUS, {"id": DEMO_SESSION_ONE_ID, "status": "FAILED", "job_name": job_name, "detail": str(exc)})


@app.post("/demo/heartwell-sadic/session-01/process", status_code=status.HTTP_202_ACCEPTED)
def process_demo_session_one(background_tasks: BackgroundTasks):
    """Submit the staged synthetic Session 01 WAV to HealthScribe for processing."""
    if not DEMO_SESSION_ONE_RECORDING.is_file():
        raise HTTPException(status_code=404, detail="Upload the Session 01 demo WAV before processing it.")
    if DEMO_SESSION_ONE_STATUS.is_file():
        try:
            previous_status = json.loads(DEMO_SESSION_ONE_STATUS.read_text(encoding="utf-8")).get("status")
        except (OSError, json.JSONDecodeError):
            previous_status = None
        if previous_status in {"IN_PROGRESS", "COMPLETED"}:
            raise HTTPException(status_code=409, detail=f"Session 01 HealthScribe processing is already {previous_status.lower()}.")
    try:
        input_bucket, output_bucket, data_role = configuration()
        job_name = f"healthscribe-demo-{datetime.now():%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
        input_key = "demo-data/heartwell-sadic/session-01/recording.wav"
        boto3.client("s3", region_name=AWS_REGION).upload_file(str(DEMO_SESSION_ONE_RECORDING), input_bucket, input_key)
        boto3.client("transcribe", region_name=AWS_REGION).start_medical_scribe_job(
            MedicalScribeJobName=job_name,
            Media={"MediaFileUri": f"s3://{input_bucket}/{input_key}"},
            OutputBucketName=output_bucket,
            DataAccessRoleArn=data_role,
            Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2},
        )
        write_json(DEMO_SESSION_ONE_STATUS, {"id": DEMO_SESSION_ONE_ID, "status": "IN_PROGRESS", "job_name": job_name})
        background_tasks.add_task(process_demo_session_one_job, job_name, input_key)
        return {"id": DEMO_SESSION_ONE_ID, "status": "IN_PROGRESS", "job_name": job_name}
    except (BotoCoreError, ClientError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not start the Session 01 HealthScribe job: {exc}") from exc


@app.post("/demo/heartwell-sadic/session-02/audio", status_code=status.HTTP_201_CREATED)
async def upload_demo_session_two_audio(audio: UploadFile = File(...)):
    """Store the explicitly synthetic Session 02 WAV with its demo case artifacts."""
    filename = audio.filename or ""
    if Path(filename).suffix.lower() != ".wav":
        raise HTTPException(status_code=415, detail="The session-two demo upload must be a WAV file.")
    if DEMO_SESSION_TWO_RECORDING.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session-two demo recording already exists. Remove it deliberately before replacing it.",
        )

    contents = await audio.read(MAX_DEMO_AUDIO_BYTES + 1)
    if len(contents) > MAX_DEMO_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="The demo recording exceeds the 100 MB limit.")
    if len(contents) < 12 or contents[:4] != b"RIFF" or contents[8:12] != b"WAVE":
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid WAV container.")

    try:
        DEMO_SESSION_TWO_DIRECTORY.mkdir(parents=True, exist_ok=True)
        DEMO_SESSION_TWO_RECORDING.write_bytes(contents)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not store the demo recording.") from exc

    return {
        "stored": True,
        "session": "heartwell-sadic/session-02",
        "path": str(DEMO_SESSION_TWO_RELATIVE_DIRECTORY / "recording.wav"),
        "bytes": len(contents),
    }


def process_demo_session_two_job(job_name: str, input_key: str) -> None:
    """Persist Session 02 HealthScribe output beside its synthetic source WAV."""
    try:
        input_bucket, _, _ = configuration()
        transcribe = boto3.client("transcribe", region_name=AWS_REGION)
        s3 = boto3.client("s3", region_name=AWS_REGION)
        while True:
            job = transcribe.get_medical_scribe_job(MedicalScribeJobName=job_name)["MedicalScribeJob"]
            state = job["MedicalScribeJobStatus"]
            if state in {"COMPLETED", "FAILED"}:
                break
            write_json(DEMO_SESSION_TWO_STATUS, {"id": DEMO_SESSION_TWO_ID, "status": state, "job_name": job_name})
            time.sleep(POLL_SECONDS)
        if state == "FAILED":
            raise RuntimeError(job.get("FailureReason", "HealthScribe did not complete the job."))

        outputs = job["MedicalScribeOutput"]
        transcript_bucket, transcript_key = s3_location(outputs["TranscriptFileUri"])
        note_bucket, note_key = s3_location(outputs["ClinicalDocumentUri"])
        raw_transcript = json.loads(s3.get_object(Bucket=transcript_bucket, Key=transcript_key)["Body"].read())
        raw_note = json.loads(s3.get_object(Bucket=note_bucket, Key=note_key)["Body"].read())
        write_json(DEMO_SESSION_TWO_DIRECTORY / "healthscribe-transcript.json", raw_transcript)
        write_json(DEMO_SESSION_TWO_DIRECTORY / "clinical-note.json", raw_note)
        segments = segments_from_healthscribe(raw_transcript)
        write_json(DEMO_SESSION_TWO_TRANSCRIPT, {
            "id": DEMO_SESSION_TWO_ID,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "audio": {"file": DEMO_SESSION_TWO_RECORDING.name, "mime_type": "audio/wav"},
            "speakers": {},
            "text": " ".join(segment["text"] for segment in segments),
            "segments": segments,
            "clinical_note": summary_from_healthscribe(raw_note),
            "healthscribe": {
                "job_name": job_name,
                "input_uri": f"s3://{input_bucket}/{input_key}",
                "transcript_uri": outputs["TranscriptFileUri"],
                "clinical_note_uri": outputs["ClinicalDocumentUri"],
            },
        })
        write_json(DEMO_SESSION_TWO_STATUS, {"id": DEMO_SESSION_TWO_ID, "status": "COMPLETED", "job_name": job_name})
    except (BotoCoreError, ClientError, KeyError, OSError, ValueError, RuntimeError) as exc:
        write_json(DEMO_SESSION_TWO_STATUS, {"id": DEMO_SESSION_TWO_ID, "status": "FAILED", "job_name": job_name, "detail": str(exc)})


@app.post("/demo/heartwell-sadic/session-02/process", status_code=status.HTTP_202_ACCEPTED)
def process_demo_session_two(background_tasks: BackgroundTasks):
    """Submit the staged synthetic Session 02 WAV to HealthScribe for processing."""
    if not DEMO_SESSION_TWO_RECORDING.is_file():
        raise HTTPException(status_code=404, detail="Upload the Session 02 demo WAV before processing it.")
    if DEMO_SESSION_TWO_STATUS.is_file():
        try:
            previous_status = json.loads(DEMO_SESSION_TWO_STATUS.read_text(encoding="utf-8")).get("status")
        except (OSError, json.JSONDecodeError):
            previous_status = None
        if previous_status == "IN_PROGRESS":
            job_name = json.loads(DEMO_SESSION_TWO_STATUS.read_text(encoding="utf-8"))["job_name"]
            input_key = "demo-data/heartwell-sadic/session-02/recording.wav"
            background_tasks.add_task(process_demo_session_two_job, job_name, input_key)
            return {"id": DEMO_SESSION_TWO_ID, "status": "IN_PROGRESS", "job_name": job_name}
        if previous_status == "COMPLETED":
            raise HTTPException(status_code=409, detail="Session 02 HealthScribe processing is already completed.")
    try:
        input_bucket, output_bucket, data_role = configuration()
        job_name = f"healthscribe-demo-{datetime.now():%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
        input_key = "demo-data/heartwell-sadic/session-02/recording.wav"
        boto3.client("s3", region_name=AWS_REGION).upload_file(str(DEMO_SESSION_TWO_RECORDING), input_bucket, input_key)
        boto3.client("transcribe", region_name=AWS_REGION).start_medical_scribe_job(
            MedicalScribeJobName=job_name,
            Media={"MediaFileUri": f"s3://{input_bucket}/{input_key}"},
            OutputBucketName=output_bucket,
            DataAccessRoleArn=data_role,
            Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2},
        )
        write_json(DEMO_SESSION_TWO_STATUS, {"id": DEMO_SESSION_TWO_ID, "status": "IN_PROGRESS", "job_name": job_name})
        background_tasks.add_task(process_demo_session_two_job, job_name, input_key)
        return {"id": DEMO_SESSION_TWO_ID, "status": "IN_PROGRESS", "job_name": job_name}
    except (BotoCoreError, ClientError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not start the Session 02 HealthScribe job: {exc}") from exc


@app.post("/demo/heartwell-sadic/session-{session_number}/audio", status_code=status.HTTP_201_CREATED)
async def upload_additional_demo_audio(session_number: int, audio: UploadFile = File(...)):
    """Stage a synthetic Session 03–06 WAV without using runtime recordings."""
    recording, _, _, _, _ = additional_demo_session_assets(session_number)
    if Path(audio.filename or "").suffix.lower() != ".wav":
        raise HTTPException(status_code=415, detail="The synthetic demo upload must be a WAV file.")
    if recording.exists():
        raise HTTPException(status_code=409, detail="A demo recording already exists. Remove it deliberately before replacing it.")
    contents = await audio.read(MAX_DEMO_AUDIO_BYTES + 1)
    if len(contents) > MAX_DEMO_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="The demo recording exceeds the 100 MB limit.")
    if len(contents) < 12 or contents[:4] != b"RIFF" or contents[8:12] != b"WAVE":
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid WAV container.")
    try:
        recording.parent.mkdir(parents=True, exist_ok=True)
        recording.write_bytes(contents)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not store the demo recording.") from exc
    return {"stored": True, "session": f"heartwell-sadic/session-{session_number:02d}", "path": str(recording.relative_to(Path(__file__).parent)), "bytes": len(contents)}


def process_additional_demo_session_job(session_number: int, job_name: str, input_key: str) -> None:
    """Download and normalize HealthScribe artifacts for synthetic Sessions 03–06."""
    recording, job_status, transcript_path, session_id, _ = additional_demo_session_assets(session_number)
    try:
        input_bucket, _, _ = configuration()
        transcribe = boto3.client("transcribe", region_name=AWS_REGION)
        s3 = boto3.client("s3", region_name=AWS_REGION)
        while True:
            job = transcribe.get_medical_scribe_job(MedicalScribeJobName=job_name)["MedicalScribeJob"]
            state = job["MedicalScribeJobStatus"]
            if state in {"COMPLETED", "FAILED"}:
                break
            write_json(job_status, {"id": session_id, "status": state, "job_name": job_name})
            time.sleep(POLL_SECONDS)
        if state == "FAILED":
            raise RuntimeError(job.get("FailureReason", "HealthScribe did not complete the job."))
        outputs = job["MedicalScribeOutput"]
        transcript_bucket, transcript_key = s3_location(outputs["TranscriptFileUri"])
        note_bucket, note_key = s3_location(outputs["ClinicalDocumentUri"])
        raw_transcript = json.loads(s3.get_object(Bucket=transcript_bucket, Key=transcript_key)["Body"].read())
        raw_note = json.loads(s3.get_object(Bucket=note_bucket, Key=note_key)["Body"].read())
        write_json(recording.parent / "healthscribe-transcript.json", raw_transcript)
        write_json(recording.parent / "clinical-note.json", raw_note)
        segments = segments_from_healthscribe(raw_transcript)
        write_json(transcript_path, {
            "id": session_id,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "audio": {"file": recording.name, "mime_type": "audio/wav"},
            "speakers": {},
            "text": " ".join(segment["text"] for segment in segments),
            "segments": segments,
            "clinical_note": summary_from_healthscribe(raw_note),
            "healthscribe": {"job_name": job_name, "input_uri": f"s3://{input_bucket}/{input_key}", "transcript_uri": outputs["TranscriptFileUri"], "clinical_note_uri": outputs["ClinicalDocumentUri"]},
        })
        write_json(job_status, {"id": session_id, "status": "COMPLETED", "job_name": job_name})
    except (BotoCoreError, ClientError, KeyError, OSError, ValueError, RuntimeError) as exc:
        write_json(job_status, {"id": session_id, "status": "FAILED", "job_name": job_name, "detail": str(exc)})


@app.post("/demo/heartwell-sadic/session-{session_number}/process", status_code=status.HTTP_202_ACCEPTED)
def process_additional_demo_session(session_number: int, background_tasks: BackgroundTasks):
    """Submit or resume one staged synthetic Session 03–06 HealthScribe job."""
    recording, job_status, _, session_id, _ = additional_demo_session_assets(session_number)
    if not recording.is_file():
        raise HTTPException(status_code=404, detail="Upload the synthetic session WAV before processing it.")
    input_key = f"demo-data/heartwell-sadic/session-{session_number:02d}/recording.wav"
    if job_status.is_file():
        try:
            previous = json.loads(job_status.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
        if previous.get("status") == "IN_PROGRESS" and previous.get("job_name"):
            background_tasks.add_task(process_additional_demo_session_job, session_number, previous["job_name"], input_key)
            return {"id": session_id, "status": "IN_PROGRESS", "job_name": previous["job_name"]}
        if previous.get("status") == "COMPLETED":
            raise HTTPException(status_code=409, detail="HealthScribe processing is already completed for this synthetic session.")
    try:
        input_bucket, output_bucket, data_role = configuration()
        job_name = f"healthscribe-demo-{datetime.now():%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
        boto3.client("s3", region_name=AWS_REGION).upload_file(str(recording), input_bucket, input_key)
        boto3.client("transcribe", region_name=AWS_REGION).start_medical_scribe_job(
            MedicalScribeJobName=job_name, Media={"MediaFileUri": f"s3://{input_bucket}/{input_key}"}, OutputBucketName=output_bucket, DataAccessRoleArn=data_role, Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2},
        )
        write_json(job_status, {"id": session_id, "status": "IN_PROGRESS", "job_name": job_name})
        background_tasks.add_task(process_additional_demo_session_job, session_number, job_name, input_key)
        return {"id": session_id, "status": "IN_PROGRESS", "job_name": job_name}
    except (BotoCoreError, ClientError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not start the synthetic HealthScribe job: {exc}") from exc


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


def process_job(session_id: str, job_name: str, input_key: str) -> None:
    """Download completed HealthScribe JSON files to the local session folder."""
    directory = session_directory(session_id)
    try:
        input_bucket, _, _ = configuration()
        transcribe = boto3.client("transcribe", region_name=AWS_REGION)
        s3 = boto3.client("s3", region_name=AWS_REGION)
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
        raw_transcript = json.loads(s3.get_object(Bucket=transcript_bucket, Key=transcript_key)["Body"].read())
        raw_note = json.loads(s3.get_object(Bucket=note_bucket, Key=note_key)["Body"].read())
        write_json(directory / "healthscribe-transcript.json", raw_transcript)
        write_json(directory / "clinical-note.json", raw_note)
        segments = segments_from_healthscribe(raw_transcript)
        recording = next(directory.glob("recording.*"))
        write_json(transcript_path(session_id), {
            "id": session_id,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "audio": {"file": recording.name, "mime_type": AUDIO_MIME_TYPES.get(recording.suffix.lower(), "application/octet-stream")},
            "speakers": {},
            "text": " ".join(segment["text"] for segment in segments),
            "segments": segments,
            "clinical_note": summary_from_healthscribe(raw_note),
            "healthscribe": {
                "job_name": job_name,
                "input_uri": f"s3://{input_bucket}/{input_key}",
                "transcript_uri": outputs["TranscriptFileUri"],
                "clinical_note_uri": outputs["ClinicalDocumentUri"],
            },
        })
        write_json(status_path(session_id), {"id": session_id, "status": "COMPLETED", "job_name": job_name})
    except (BotoCoreError, ClientError, KeyError, OSError, ValueError, RuntimeError) as exc:
        write_json(status_path(session_id), {"id": session_id, "status": "FAILED", "job_name": job_name, "detail": str(exc)})


@app.get("/")
def page():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/recordings/{session_id}/{filename}")
def session_recording(session_id: str, filename: str):
    path = session_directory(session_id) / Path(filename).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Recording not found.")
    return FileResponse(path, media_type=AUDIO_MIME_TYPES.get(path.suffix.lower(), "application/octet-stream"), filename=path.name)


@app.get("/demo/heartwell-sadic/session-01/recording")
def demo_session_one_recording():
    """Serve the synthetic Session 01 WAV for existing transcript playback UI."""
    if not DEMO_SESSION_ONE_RECORDING.is_file():
        raise HTTPException(status_code=404, detail="Session 01 demo recording not found.")
    return FileResponse(DEMO_SESSION_ONE_RECORDING, media_type="audio/wav", filename=DEMO_SESSION_ONE_RECORDING.name)


@app.get("/demo/heartwell-sadic/session-02/recording")
def demo_session_two_recording():
    """Serve the synthetic Session 02 WAV for existing transcript playback UI."""
    if not DEMO_SESSION_TWO_RECORDING.is_file():
        raise HTTPException(status_code=404, detail="Session 02 demo recording not found.")
    return FileResponse(DEMO_SESSION_TWO_RECORDING, media_type="audio/wav", filename=DEMO_SESSION_TWO_RECORDING.name)


@app.get("/demo/heartwell-sadic/session-{session_number}/recording")
def additional_demo_session_recording(session_number: int):
    """Serve a synthetic Session 03–06 WAV for transcript playback."""
    recording, _, _, _, _ = additional_demo_session_assets(session_number)
    if not recording.is_file():
        raise HTTPException(status_code=404, detail="Synthetic demo recording not found.")
    return FileResponse(recording, media_type="audio/wav", filename=recording.name)


@app.get("/transcripts")
def transcripts():
    items = []
    for path in RECORDINGS_DIRECTORY.glob("*/transcript.json") if RECORDINGS_DIRECTORY.exists() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append({"id": path.parent.name, "label": path.parent.name, "text": data.get("text", ""), "created_at": data.get("created_at", "")})
        except (OSError, json.JSONDecodeError):
            continue
    if DEMO_SESSION_ONE_TRANSCRIPT.is_file():
        try:
            data = json.loads(DEMO_SESSION_ONE_TRANSCRIPT.read_text(encoding="utf-8"))
            items.append({
                "id": DEMO_SESSION_ONE_ID,
                "label": "Synthetic · Elena Sadić · Session 01",
                "text": data.get("text", ""),
                "created_at": data.get("created_at", ""),
            })
        except (OSError, json.JSONDecodeError):
            pass
    if DEMO_SESSION_TWO_TRANSCRIPT.is_file():
        try:
            data = json.loads(DEMO_SESSION_TWO_TRANSCRIPT.read_text(encoding="utf-8"))
            items.append({
                "id": DEMO_SESSION_TWO_ID,
                "label": "Synthetic · Elena Sadić · Session 02",
                "text": data.get("text", ""),
                "created_at": data.get("created_at", ""),
            })
        except (OSError, json.JSONDecodeError):
            pass
    for session_number in DEMO_SESSION_SLUGS:
        _, _, path, session_id, label = additional_demo_session_assets(session_number)
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append({"id": session_id, "label": label, "text": data.get("text", ""), "created_at": data.get("created_at", "")})
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(items, key=lambda item: item["created_at"], reverse=True)


@app.get("/transcripts/{session_id}")
def transcript(session_id: str):
    demo_assets = demo_session_assets(session_id)
    path = demo_assets[2] if demo_assets else transcript_path(session_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Transcript not found.")
    data = json.loads(path.read_text(encoding="utf-8"))
    additional_number = additional_demo_session_number(session_id)
    if is_demo_session_one(session_id):
        data["recording_url"] = "/demo/heartwell-sadic/session-01/recording"
    elif is_demo_session_two(session_id):
        data["recording_url"] = "/demo/heartwell-sadic/session-02/recording"
    elif additional_number is not None:
        data["recording_url"] = f"/demo/heartwell-sadic/session-{additional_number:02d}/recording"
    else:
        data["recording_url"] = f"/recordings/{session_id}/{data['audio']['file']}"
    return data


@app.get("/transcripts/{session_id}/status")
def job_status(session_id: str):
    demo_assets = demo_session_assets(session_id)
    path = demo_assets[1] if demo_assets else status_path(session_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Processing status not found.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.put("/transcripts/{session_id}/speakers")
def save_speaker_labels(session_id: str, labels: dict[str, str] = Body(...)):
    demo_assets = demo_session_assets(session_id)
    path = demo_assets[2] if demo_assets else transcript_path(session_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Transcript not found.")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["speakers"] = {key.strip(): value.strip() for key, value in labels.items() if key.strip() and value.strip()}
    write_json(path, data)
    return {"speakers": data["speakers"]}


@app.post("/transcribe", status_code=202)
async def transcribe(background_tasks: BackgroundTasks, audio: UploadFile = File(...)):
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
    try:
        input_bucket, output_bucket, data_role = configuration()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    session_id = f"session-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    job_name = f"healthscribe-{datetime.now():%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
    directory = session_directory(session_id)
    input_key = f"recordings/{session_id}/recording{suffix}"
    try:
        directory.mkdir(parents=True)
        recording = directory / f"recording{suffix}"
        recording.write_bytes(content)
        boto3.client("s3", region_name=AWS_REGION).upload_file(str(recording), input_bucket, input_key)
        boto3.client("transcribe", region_name=AWS_REGION).start_medical_scribe_job(
            MedicalScribeJobName=job_name,
            Media={"MediaFileUri": f"s3://{input_bucket}/{input_key}"},
            OutputBucketName=output_bucket,
            DataAccessRoleArn=data_role,
            Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2},
        )
        write_json(status_path(session_id), {"id": session_id, "status": "IN_PROGRESS", "job_name": job_name})
        background_tasks.add_task(process_job, session_id, job_name, input_key)
        return {"id": session_id, "status": "IN_PROGRESS"}
    except (BotoCoreError, ClientError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not start HealthScribe job: {exc}") from exc
