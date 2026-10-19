"""Client-owned insurance-card upload, extraction, and correction workflow."""
from __future__ import annotations

import hashlib
import logging
import os
import re
from uuid import UUID, uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.routing import APIRoute
from psycopg import Error as PsycopgError
from psycopg.types.json import Json
from pydantic import BaseModel, Field, field_validator

from ai_harness.insurance_card import INSURANCE_FIELD_KEYS, extract_insurance_card
from database.auth import validate_access_token
from database.connection import connect


LOGGER = logging.getLogger(__name__)
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


class InsuranceRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def guarded(request):
            try:
                return await handler(request)
            except (PsycopgError, BotoCoreError, ClientError, RuntimeError) as exc:
                raise HTTPException(503, "The insurance-card service is temporarily unavailable. Please try again.") from exc
        return guarded


router = APIRouter(route_class=InsuranceRoute)


class InsuranceFieldsUpdate(BaseModel):
    fields: dict[str, str | None] = Field(default_factory=dict)

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, fields: dict[str, str | None]) -> dict[str, str | None]:
        if set(fields) != set(INSURANCE_FIELD_KEYS):
            raise ValueError("Submit every supported insurance field and no additional fields.")
        cleaned: dict[str, str | None] = {}
        for key in INSURANCE_FIELD_KEYS:
            value = fields[key]
            if value is not None and not isinstance(value, str):
                raise ValueError("Insurance field values must be text or null.")
            if isinstance(value, str):
                value = value.strip()
                if len(value) > 500 or any(ord(char) < 32 for char in value):
                    raise ValueError("Insurance field values must be 500 characters or fewer.")
            cleaned[key] = value or None
        return cleaned


def _client_context(connection, authorization: str | None) -> dict:
    claims = validate_access_token(authorization)
    with connection.cursor() as cursor:
        cursor.execute("""SELECT client.organization_id, client.id AS client_id,
                (SELECT id FROM app.application_users WHERE auth0_subject=%s AND status='active') AS actor_user_id
            FROM app.client_portal_accounts portal
            JOIN app.clients client ON client.id=portal.client_id
            JOIN app.organizations organization ON organization.id=client.organization_id
            WHERE portal.auth0_subject=%s AND portal.status='active'
              AND client.status='active' AND organization.status='active'""",
            (claims["sub"], claims["sub"]))
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise HTTPException(status_code=403, detail="An active client account is required.")
    return {**rows[0], "subject": claims["sub"]}


def _therapist_context(connection, authorization: str | None, client_id: str) -> dict:
    claims = validate_access_token(authorization)
    try:
        client_id = str(UUID(client_id))
    except ValueError as exc:
        raise HTTPException(422, "Invalid client identifier.") from exc
    with connection.cursor() as cursor:
        cursor.execute("""SELECT DISTINCT client.organization_id, client.id AS client_id,
                actor.id AS actor_user_id, practitioner.id AS practitioner_id
            FROM app.application_users actor
            JOIN app.organization_memberships membership ON membership.user_id=actor.id
            JOIN app.organization_practitioners practitioner ON practitioner.membership_id=membership.id
              AND practitioner.organization_id=membership.organization_id
            JOIN app.client_therapist_access access ON access.practitioner_id=practitioner.id
              AND access.organization_id=membership.organization_id
            JOIN app.clients client ON client.id=access.client_id
              AND client.organization_id=access.organization_id
            WHERE actor.auth0_subject=%s AND actor.status='active'
              AND membership.status='active' AND membership.starts_at<=CURRENT_TIMESTAMP
              AND (membership.ends_at IS NULL OR membership.ends_at>CURRENT_TIMESTAMP)
              AND practitioner.status='active' AND client.status='active' AND client.id=%s
              AND access.revoked_at IS NULL AND access.can_read_clinical
              AND access.effective_from<=CURRENT_TIMESTAMP
              AND (access.effective_until IS NULL OR access.effective_until>CURRENT_TIMESTAMP)""",
            (claims["sub"], client_id))
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise HTTPException(403, "This client's insurance information is not available for your account.")
    return rows[0]


def _valid_image(data: bytes, content_type: str) -> bool:
    return (
        (content_type == "image/jpeg" and data.startswith(b"\xff\xd8\xff"))
        or (content_type == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n"))
        or (content_type == "image/webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP")
    )


def _read_image(upload: UploadFile) -> tuple[bytes, str]:
    content_type = (upload.content_type or "").lower()
    data = upload.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES or content_type not in ALLOWED_IMAGE_TYPES or not _valid_image(data, content_type):
        raise HTTPException(400, "Choose JPEG, PNG, or WebP images no larger than 5 MB each.")
    return data, content_type


def _safe_filename(filename: str | None, content_type: str, side: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._ -]", "_", (filename or f"{side}{ALLOWED_IMAGE_TYPES[content_type]}").replace("\\", "/").split("/")[-1])[:160]
    return name or f"{side}{ALLOWED_IMAGE_TYPES[content_type]}"


def _card_response(row: dict | None) -> dict:
    if not row:
        return {"card": None}
    extracted = row.get("model_extracted_fields") or {}
    corrected = row.get("client_corrected_fields")
    effective = corrected if isinstance(corrected, dict) else extracted
    return {"card": {
        "id": str(row["id"]),
        "status": row["status"],
        "frontFilename": row["front_filename"],
        "backFilename": row["back_filename"],
        "fields": {key: effective.get(key) for key in INSURANCE_FIELD_KEYS},
        "source": "client" if isinstance(corrected, dict) else "openai",
        "model": row.get("source_model"),
        "analyzedAt": row["analyzed_at"].isoformat() if row.get("analyzed_at") else None,
        "updatedAt": row["updated_at"].isoformat(),
    }}


def _therapist_card_response(row: dict | None) -> dict:
    if not row:
        return {"card": None}
    extracted = row.get("model_extracted_fields") or {}
    corrected = row.get("client_corrected_fields")
    effective = corrected if isinstance(corrected, dict) else extracted
    return {"card": {
        "id": str(row["id"]),
        "status": row["status"],
        "fields": {key: effective.get(key) for key in INSURANCE_FIELD_KEYS},
        "clientReviewed": isinstance(corrected, dict),
        "updatedAt": row["updated_at"].isoformat(),
    }}


def _active_card(connection, context: dict, *, lock: bool = False) -> dict | None:
    with connection.cursor() as cursor:
        cursor.execute("""SELECT * FROM app.client_insurance_cards
            WHERE organization_id=%s AND client_id=%s AND status<>'replaced'
            ORDER BY created_at DESC LIMIT 1""" + (" FOR UPDATE" if lock else ""),
            (context["organization_id"], context["client_id"]))
        return cursor.fetchone()


def _audit(connection, context: dict, action: str, card_id, outcome: str = "allowed") -> None:
    with connection.cursor() as cursor:
        cursor.execute("""INSERT INTO app.audit_events
            (organization_id, actor_user_id, action, target_type, target_id, outcome)
            VALUES (%s,%s,%s,'client_insurance_card',%s,%s)""",
            (context["organization_id"], context.get("actor_user_id"), action, card_id, outcome))


@router.get("/account/insurance-card")
def get_insurance_card(authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = _client_context(connection, authorization)
        row = _active_card(connection, context)
    return _card_response(row)


@router.get("/clients/{client_id}/insurance-card")
def get_client_insurance_card(client_id: str, authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = _therapist_context(connection, authorization, client_id)
        row = _active_card(connection, context)
        if row:
            _audit(connection, context, "insurance_card.view", row["id"])
    return _therapist_card_response(row)


@router.post("/account/insurance-card", status_code=201)
async def upload_insurance_card(
    front: UploadFile = File(...),
    back: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    enabled = os.getenv("INSURANCE_CARD_OPENAI_APPROVED", "false").strip().lower() in {"1", "true", "yes", "on"}
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("INSURANCE_CARD_MODEL")
    if not enabled or not api_key or not model:
        raise HTTPException(503, "Insurance-card analysis has not been approved and configured for this environment.")

    front_data, front_type = _read_image(front)
    back_data, back_type = _read_image(back)
    card_id = uuid4()

    with connect() as connection:
        context = _client_context(connection, authorization)
        with connection.cursor() as cursor:
            cursor.execute("SELECT bucket, region, kms_key_arn FROM app.organization_storage WHERE organization_id=%s", (context["organization_id"],))
            storage = cursor.fetchone()
        if not storage:
            raise HTTPException(503, "Private insurance-card storage is not configured for this account.")

        prefix = f"clients/{context['client_id']}/insurance-cards/{card_id}/"
        front_key = f"{prefix}front-{uuid4().hex}{ALLOWED_IMAGE_TYPES[front_type]}"
        back_key = f"{prefix}back-{uuid4().hex}{ALLOWED_IMAGE_TYPES[back_type]}"
        s3 = boto3.client("s3", region_name=storage["region"])
        front_result = s3.put_object(
            Bucket=storage["bucket"], Key=front_key, Body=front_data, ContentType=front_type,
            ServerSideEncryption="aws:kms", SSEKMSKeyId=storage["kms_key_arn"],
        )
        back_result = s3.put_object(
            Bucket=storage["bucket"], Key=back_key, Body=back_data, ContentType=back_type,
            ServerSideEncryption="aws:kms", SSEKMSKeyId=storage["kms_key_arn"],
        )
        with connection.cursor() as cursor:
            artifact_ids = []
            for side, data, content_type, key, result in (
                ("front", front_data, front_type, front_key, front_result),
                ("back", back_data, back_type, back_key, back_result),
            ):
                cursor.execute("""INSERT INTO app.clinical_artifacts
                    (organization_id, client_id, artifact_type, source, storage_bucket, object_key,
                     object_version_id, content_type, byte_size, sha256_checksum, encryption_key_reference)
                    VALUES (%s,%s,'attachment','user_upload',%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (context["organization_id"], context["client_id"], storage["bucket"], key,
                     result.get("VersionId"), content_type, len(data), hashlib.sha256(data).hexdigest(), storage["kms_key_arn"]))
                artifact_ids.append(cursor.fetchone()["id"])
            cursor.execute("""UPDATE app.client_insurance_cards SET status='replaced'
                WHERE organization_id=%s AND client_id=%s AND status<>'replaced'""",
                (context["organization_id"], context["client_id"]))
            cursor.execute("""INSERT INTO app.client_insurance_cards
                (id, organization_id, client_id, front_artifact_id, back_artifact_id,
                 front_filename, back_filename, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'processing')""",
                (card_id, context["organization_id"], context["client_id"], *artifact_ids,
                 _safe_filename(front.filename, front_type, "front"), _safe_filename(back.filename, back_type, "back")))
        _audit(connection, context, "insurance_card.upload", card_id)

    try:
        fields, metadata = extract_insurance_card(
            front=front_data, front_content_type=front_type,
            back=back_data, back_content_type=back_type,
            api_key=api_key, model=model,
        )
    except RuntimeError as exc:
        LOGGER.warning("Insurance-card analysis failed (%s).", type(exc).__name__)
        with connect() as connection:
            context = _client_context(connection, authorization)
            with connection.cursor() as cursor:
                cursor.execute("""UPDATE app.client_insurance_cards SET status='failed'
                    WHERE id=%s AND organization_id=%s AND client_id=%s AND status='processing'""",
                    (card_id, context["organization_id"], context["client_id"]))
            _audit(connection, context, "insurance_card.analyze", card_id, "failed")
        raise HTTPException(502, "The card was stored, but its details could not be analyzed. Upload it again to retry.") from exc

    with connect() as connection:
        context = _client_context(connection, authorization)
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE app.client_insurance_cards
                SET status='ready', model_extracted_fields=%s, source_provider=%s,
                    source_model=%s, source_response_id=%s, analyzed_at=CURRENT_TIMESTAMP
                WHERE id=%s AND organization_id=%s AND client_id=%s AND status='processing'
                RETURNING *""",
                (Json(fields), metadata["provider"], metadata["model"], metadata["response_id"],
                 card_id, context["organization_id"], context["client_id"]))
            row = cursor.fetchone()
        if not row:
            raise HTTPException(409, "The insurance card is no longer active.")
        _audit(connection, context, "insurance_card.analyze", card_id)
    return _card_response(row)


@router.put("/account/insurance-card")
def update_insurance_fields(request: InsuranceFieldsUpdate, authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = _client_context(connection, authorization)
        card = _active_card(connection, context, lock=True)
        if not card:
            raise HTTPException(404, "Insurance card not found.")
        if card["status"] != "ready":
            raise HTTPException(409, "Insurance details are not ready to edit.")
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE app.client_insurance_cards
                SET client_corrected_fields=%s, corrected_at=CURRENT_TIMESTAMP
                WHERE id=%s AND organization_id=%s AND client_id=%s RETURNING *""",
                (Json(request.fields), card["id"], context["organization_id"], context["client_id"]))
            row = cursor.fetchone()
        _audit(connection, context, "insurance_card.correct", card["id"])
    return _card_response(row)
