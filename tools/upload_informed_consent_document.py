"""Seed the demonstration informed-consent PDF into Elena's organization storage."""

import hashlib
from pathlib import Path
from uuid import uuid4

import boto3
from dotenv import load_dotenv

from database.connection import connect


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "output" / "pdf" / "informed-consent-therapy-recording-ai-documentation.pdf"
THUMBNAIL = ROOT / "output" / "pdf" / "informed-consent-therapy-recording-ai-documentation-thumbnail.png"
PAGE_GLOB = "informed-consent-therapy-recording-ai-documentation-page-*.png"
TITLE = "Informed Consent for Therapy, Session Recording, Transcription, and AI-Assisted Documentation"
FILENAME = "informed-consent-therapy-recording-ai-documentation.pdf"


def put(s3, storage, path, key, content_type):
    body = path.read_bytes()
    result = s3.put_object(Bucket=storage["bucket"], Key=key, Body=body, ContentType=content_type,
                           ServerSideEncryption="aws:kms", SSEKMSKeyId=storage["kms_key_arn"])
    return body, result.get("VersionId")


def insert_artifact(cursor, context, key, version_id, content_type, body):
    cursor.execute("""INSERT INTO app.clinical_artifacts
        (organization_id, client_id, artifact_type, source, storage_bucket, object_key,
         object_version_id, content_type, byte_size, sha256_checksum, encryption_key_reference)
        VALUES (%s,%s,'attachment','application',%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (context["organization_id"], context["client_id"], context["bucket"], key, version_id,
         content_type, len(body), hashlib.sha256(body).hexdigest(), context["kms_key_arn"]))
    return cursor.fetchone()["id"]


def main():
    load_dotenv(ROOT / ".env", override=True)
    pages = sorted(PDF.parent.glob(PAGE_GLOB), key=lambda path: int(path.stem.rsplit("-", 1)[1]))
    if not PDF.is_file() or not THUMBNAIL.is_file() or not pages:
        raise RuntimeError("Generate the consent PDF, thumbnail, and rendered pages before uploading.")
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT client.id AS client_id, client.organization_id,
                storage.bucket, storage.region, storage.kms_key_arn, actor.id AS actor_user_id
            FROM app.client_portal_accounts portal
            JOIN app.clients client ON client.id=portal.client_id
            JOIN app.organization_storage storage ON storage.organization_id=client.organization_id
            JOIN app.client_therapist_access access
              ON access.client_id=client.id AND access.organization_id=client.organization_id
            JOIN app.organization_practitioners practitioner ON practitioner.id=access.practitioner_id
            JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id
            JOIN app.application_users actor ON actor.id=membership.user_id
            WHERE portal.synthetic_case_key='heartwell-sadic' AND client.status='active'
              AND access.revoked_at IS NULL AND access.can_read_clinical
              AND actor.status='active' AND membership.status='active' AND practitioner.status='active'
            ORDER BY CASE access.relationship_type WHEN 'primary' THEN 0 ELSE 1 END
            LIMIT 1""")
        context = cursor.fetchone()
        if not context:
            raise RuntimeError("The Elena/Jeremy care relationship or organization storage is unavailable.")
        cursor.execute("""SELECT id FROM app.client_documents
            WHERE organization_id=%s AND client_id=%s AND title=%s AND status='active'""",
            (context["organization_id"], context["client_id"], TITLE))
        existing = cursor.fetchone()
        document_id = existing["id"] if existing else uuid4()
        prefix = f"clients/{context['client_id']}/documents/{document_id}/"
        s3 = boto3.client("s3", region_name=context["region"])
        if not existing:
            pdf_key = f"{prefix}{FILENAME}"
            thumbnail_key = f"{prefix}thumbnail.png"
            pdf_body, pdf_version = put(s3, context, PDF, pdf_key, "application/pdf")
            thumbnail_body, thumbnail_version = put(s3, context, THUMBNAIL, thumbnail_key, "image/png")
            content_artifact_id = insert_artifact(cursor, context, pdf_key, pdf_version, "application/pdf", pdf_body)
            thumbnail_artifact_id = insert_artifact(cursor, context, thumbnail_key, thumbnail_version, "image/png", thumbnail_body)
            cursor.execute("""INSERT INTO app.client_documents
                (id, organization_id, client_id, title, document_type, source_filename,
                 content_artifact_id, thumbnail_artifact_id, uploaded_by_user_id)
                VALUES (%s,%s,%s,%s,'consent_form',%s,%s,%s,%s)""",
                (document_id, context["organization_id"], context["client_id"], TITLE, FILENAME,
                 content_artifact_id, thumbnail_artifact_id, context["actor_user_id"]))

        cursor.execute("SELECT page_number FROM app.client_document_pages WHERE document_id=%s",
                       (document_id,))
        existing_pages = {row["page_number"] for row in cursor.fetchall()}
        uploaded_pages = 0
        for page_number, page_path in enumerate(pages, 1):
            if page_number in existing_pages:
                continue
            page_key = f"{prefix}pages/page-{page_number}.png"
            page_body, page_version = put(s3, context, page_path, page_key, "image/png")
            page_artifact_id = insert_artifact(
                cursor, context, page_key, page_version, "image/png", page_body)
            cursor.execute("""INSERT INTO app.client_document_pages
                (document_id, page_number, artifact_id) VALUES (%s,%s,%s)""",
                (document_id, page_number, page_artifact_id))
            uploaded_pages += 1
        print(f"Document ready: {document_id}; uploaded {uploaded_pages} rendered page(s)")


if __name__ == "__main__":
    main()
