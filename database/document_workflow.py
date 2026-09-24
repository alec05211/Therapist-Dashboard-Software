"""Private, relationship-scoped PDF upload and client signature workflow."""
import hashlib
from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID, uuid4
from xml.sax.saxutils import escape
from threading import Lock

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.routing import APIRoute
from fastapi.responses import Response
from psycopg import Error as PsycopgError
from pydantic import BaseModel, Field
from pypdf import PdfReader, PdfWriter
import pypdfium2 as pdfium
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from database.auth import validate_access_token
from database.connection import connect

class DocumentRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def guarded(request):
            try:
                return await handler(request)
            except (PsycopgError, RuntimeError, BotoCoreError, ClientError) as exc:
                raise HTTPException(503, 'The document service is temporarily unavailable. Please try again.') from exc
        return guarded


router = APIRouter(route_class=DocumentRoute)
MAX_BYTES = 20 * 1024 * 1024
RENDER_LOCK = Lock()  # PDFium calls must not run concurrently within a process.
CONSENT = "I have read this document and agree to sign it electronically using my typed name."


def relationships(connection, subject):
    with connection.cursor() as cursor:
        cursor.execute("""SELECT DISTINCT client.organization_id, client.id AS client_id,
                practitioner.id AS practitioner_id, practitioner.professional_name,
                actor.id AS actor_id, NULL::uuid AS portal_id, 'therapist' AS role,
                access.can_write_clinical AS can_upload
            FROM app.client_therapist_access access
            JOIN app.clients client ON client.id=access.client_id AND client.organization_id=access.organization_id
            JOIN app.organizations organization ON organization.id=client.organization_id AND organization.status='active'
            JOIN app.organization_practitioners practitioner ON practitioner.id=access.practitioner_id
              AND practitioner.organization_id=client.organization_id
            JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id
              AND membership.organization_id=client.organization_id
            JOIN app.application_users actor ON actor.id=membership.user_id
            WHERE actor.auth0_subject=%s AND actor.status='active' AND membership.status='active'
              AND membership.starts_at<=CURRENT_TIMESTAMP
              AND (membership.ends_at IS NULL OR membership.ends_at>CURRENT_TIMESTAMP)
              AND practitioner.status='active' AND client.status='active'
              AND access.revoked_at IS NULL AND access.can_read_clinical
              AND access.effective_from<=CURRENT_TIMESTAMP
              AND (access.effective_until IS NULL OR access.effective_until>CURRENT_TIMESTAMP)
            UNION
            SELECT DISTINCT client.organization_id, client.id, practitioner.id,
                practitioner.professional_name, NULL::uuid, portal.id, 'client', false
            FROM app.client_portal_accounts portal
            JOIN app.clients client ON client.id=portal.client_id
            JOIN app.organizations organization ON organization.id=client.organization_id AND organization.status='active'
            JOIN app.client_therapist_access access ON access.client_id=client.id AND access.organization_id=client.organization_id
            JOIN app.organization_practitioners practitioner ON practitioner.id=access.practitioner_id
              AND practitioner.organization_id=client.organization_id
            JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id
              AND membership.organization_id=client.organization_id
            JOIN app.application_users actor ON actor.id=membership.user_id
            WHERE portal.auth0_subject=%s AND portal.status='active' AND client.status='active'
              AND actor.status='active' AND practitioner.status='active' AND membership.status='active'
              AND membership.starts_at<=CURRENT_TIMESTAMP
              AND (membership.ends_at IS NULL OR membership.ends_at>CURRENT_TIMESTAMP)
              AND access.revoked_at IS NULL AND access.can_read_clinical
              AND access.effective_from<=CURRENT_TIMESTAMP
              AND (access.effective_until IS NULL OR access.effective_until>CURRENT_TIMESTAMP)""", (subject, subject))
        return cursor.fetchall()


def authorize(connection, authorization, organization_id, client_id, practitioner_id=None):
    claims = validate_access_token(authorization)
    try:
        organization_id, client_id = str(UUID(organization_id)), str(UUID(client_id))
        if practitioner_id:
            practitioner_id = str(UUID(practitioner_id))
    except ValueError as exc:
        raise HTTPException(422, "Invalid document relationship.") from exc
    rows = [row for row in relationships(connection, claims['sub'])
            if str(row['organization_id']) == organization_id and str(row['client_id']) == client_id
            and (not practitioner_id or str(row['practitioner_id']) == practitioner_id)]
    # Multiple grants to the same practitioner are one shared document space.
    unique = {}
    for row in rows:
        key = (str(row['practitioner_id']), row['role'])
        if key not in unique or row['can_upload']:
            unique[key] = row
    if len(unique) != 1:
        raise HTTPException(403, "Select an active client-therapist relationship.")
    return next(iter(unique.values()))


def scope(context):
    return (context['organization_id'], context['client_id'], context['practitioner_id'])


def document_row(connection, context, document_id, lock=False):
    try:
        document_id = str(UUID(document_id))
    except ValueError as exc:
        raise HTTPException(404, "Document not found.") from exc
    with connection.cursor() as cursor:
        cursor.execute("""SELECT * FROM app.client_documents WHERE organization_id=%s
            AND client_id=%s AND practitioner_id=%s AND id=%s
            AND status='active' AND deleted_at IS NULL""" + (" FOR UPDATE" if lock else ""),
            (*scope(context), document_id))
        row = cursor.fetchone()
    if not row:
        raise HTTPException(404, "Document not found.")
    return row


def read_artifact(connection, context, artifact_id):
    with connection.cursor() as cursor:
        cursor.execute("""SELECT artifact.*, storage.region FROM app.clinical_artifacts artifact
            JOIN app.organization_storage storage ON storage.organization_id=artifact.organization_id
            WHERE artifact.id=%s AND artifact.organization_id=%s AND artifact.client_id=%s
              AND artifact.lifecycle_state='active' AND artifact.deleted_at IS NULL""",
            (artifact_id, context['organization_id'], context['client_id']))
        artifact = cursor.fetchone()
    if not artifact:
        raise HTTPException(404, "Document file not found.")
    args = dict(Bucket=artifact['storage_bucket'], Key=artifact['object_key'])
    if artifact['object_version_id']:
        args['VersionId'] = artifact['object_version_id']
    result = boto3.client('s3', region_name=artifact['region']).get_object(**args)
    stream = result['Body']
    try:
        body = stream.read(MAX_BYTES + 1)
    finally:
        stream.close()
    if len(body) > MAX_BYTES:
        raise HTTPException(413, "Document exceeds the 20 MB limit.")
    return body, artifact['content_type']


def save_artifact(connection, context, document_id, body, kind, content_type='application/pdf'):
    with connection.cursor() as cursor:
        cursor.execute('SELECT * FROM app.organization_storage WHERE organization_id=%s', (context['organization_id'],))
        storage = cursor.fetchone()
        if not storage:
            raise HTTPException(503, "Private document storage is not configured.")
        extension = 'png' if content_type == 'image/png' else 'pdf'
        key = f"clients/{context['client_id']}/practitioners/{context['practitioner_id']}/documents/{document_id}/{kind}-{uuid4()}.{extension}"
        result = boto3.client('s3', region_name=storage['region']).put_object(
            Bucket=storage['bucket'], Key=key, Body=body, ContentType=content_type,
            ServerSideEncryption='aws:kms', SSEKMSKeyId=storage['kms_key_arn'])
        cursor.execute("""INSERT INTO app.clinical_artifacts
            (organization_id, client_id, artifact_type, source, storage_bucket, object_key,
             object_version_id, content_type, byte_size, sha256_checksum, encryption_key_reference)
            VALUES (%s,%s,'attachment','application',%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (context['organization_id'], context['client_id'], storage['bucket'], key,
             result.get('VersionId'), content_type, len(body), hashlib.sha256(body).hexdigest(), storage['kms_key_arn']))
        return cursor.fetchone()['id']


def validate_pdf(body):
    if not body.startswith(b'%PDF-'):
        raise HTTPException(422, "Choose a valid PDF document.")
    try:
        reader = PdfReader(BytesIO(body))
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 100:
            raise ValueError('Unsupported PDF')
        # Active content and attached files do not belong in the shared viewer.
        root = reader.trailer['/Root']
        if any(key in root for key in ('/OpenAction', '/AA')) or reader.attachments:
            raise ValueError('Active PDF')
        names = root.get('/Names')
        if names and '/JavaScript' in names.get_object():
            raise ValueError('Active PDF')
        for page in reader.pages:
            if '/AA' in page:
                raise ValueError('Active PDF')
            for annotation in page.get('/Annots', []):
                item = annotation.get_object()
                if '/A' in item or '/AA' in item or item.get('/Subtype') in ('/RichMedia', '/FileAttachment'):
                    raise ValueError('Active PDF')
        return reader
    except Exception as exc:
        raise HTTPException(422, "Use an unencrypted PDF with 1–100 pages and no active content or attachments.") from exc


def signed_pdf(body, name, signed_at, document_id):
    reader = validate_pdf(body)
    receipt = BytesIO()
    styles = getSampleStyleSheet()
    digest = hashlib.sha256(body).hexdigest()
    paragraphs = [Paragraph('Electronic signature', styles['Title']), Spacer(1, 24)]
    for label, value in [('Signed by', name), ('Signed at (UTC)', signed_at.isoformat()),
                         ('Document ID', str(document_id)), ('Original PDF SHA-256', digest),
                         ('Agreement', CONSENT)]:
        paragraphs.extend([Paragraph(escape(label), styles['Heading3']),
                           Paragraph(escape(value), styles['BodyText']), Spacer(1, 12)])
    SimpleDocTemplate(receipt).build(paragraphs)
    writer = PdfWriter()
    writer.append(reader)
    writer.append(PdfReader(receipt))
    output = BytesIO()
    writer.write(output)
    if output.tell() > MAX_BYTES:
        raise HTTPException(413, "The signed PDF exceeds the 20 MB limit.")
    return output.getvalue()


def render_page(body, page_number):
    with RENDER_LOCK:
        try:
            with pdfium.PdfDocument(body) as pdf:
                if not 1 <= page_number <= len(pdf):
                    raise HTTPException(404, 'Document page not found.')
                page = pdf[page_number - 1]
                try:
                    width, height = page.get_size()
                    bitmap = page.render(scale=min(1100 / max(width, 1), 1600 / max(height, 1)))
                    try:
                        output = BytesIO()
                        bitmap.to_pil().save(output, format='PNG')
                        return output.getvalue()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
        except pdfium.PdfiumError as exc:
            raise HTTPException(422, 'This PDF could not be displayed. Please use another PDF.') from exc


@router.get('/document-relationships')
def get_relationships(authorization: str | None = Header(default=None)):
    claims = validate_access_token(authorization)
    with connect() as connection:
        rows = relationships(connection, claims['sub'])
    contexts = {}
    for row in rows:
        key = tuple(str(row[k]) for k in ('organization_id', 'client_id', 'practitioner_id'))
        contexts[key] = dict(organizationId=key[0], clientId=key[1], practitionerId=key[2],
                             therapistName=row['professional_name'] or 'Therapist')
    return {'relationships': list(contexts.values())}


@router.get('/clinical-records/clients/{client_id}/documents')
def list_documents(client_id: str, organization_id: str, practitioner_id: str | None = None,
                   authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = authorize(connection, authorization, organization_id, client_id, practitioner_id)
        with connection.cursor() as cursor:
            cursor.execute("""SELECT document.*, artifact.byte_size,
                COALESCE(document.pdf_page_count,
                  (SELECT count(*) FROM app.client_document_pages page WHERE page.document_id=document.id)) AS page_count
                FROM app.client_documents document
                JOIN app.clinical_artifacts artifact ON artifact.id=document.content_artifact_id
                WHERE document.organization_id=%s AND document.client_id=%s AND document.practitioner_id=%s
                  AND document.status='active' AND document.deleted_at IS NULL
                  AND artifact.lifecycle_state='active' AND artifact.deleted_at IS NULL
                ORDER BY document.created_at DESC""", scope(context))
            rows = cursor.fetchall()
    records = []
    for row in rows:
        base = f"/api/clinical-records/clients/{client_id}/documents/{row['id']}"
        query = f"?organization_id={organization_id}&practitioner_id={context['practitioner_id']}"
        records.append(dict(id=str(row['id']), title=row['title'], documentType=row['document_type'],
            filename=row['source_filename'], version=row['version_number'], createdAt=row['created_at'].isoformat(),
            contentType='application/pdf', byteSize=row['byte_size'], workflowStatus=row['workflow_status'],
            pageCount=row['page_count'], pageUrls=[base+f'/pages/{number}'+query for number in range(1, row['page_count']+1)],
            thumbnailUrl=base+'/thumbnail'+query if row['thumbnail_artifact_id'] else None, contentUrl=base+'/content'+query,
            signedUrl=base+'/signed'+query if row['signed_artifact_id'] else None,
            signedPageUrls=[base+f'/pages/{number}'+query+'&signed=true' for number in range(1, row['page_count']+2)] if row['signed_artifact_id'] else [],
            signedAt=row['signed_at'].isoformat() if row['signed_at'] else None, signerName=row['signer_name']))
    return dict(documents=records, canUpload=context['role']=='therapist' and context['can_upload'],
                canSign=context['role']=='client', practitionerId=str(context['practitioner_id']))


@router.post('/clinical-records/clients/{client_id}/documents', status_code=201)
def upload_document(client_id: str, organization_id: str, file: UploadFile = File(...),
                    title: str = Form(..., min_length=1, max_length=200),
                    request_signature: bool = Form(False), practitioner_id: str | None = None,
                    authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = authorize(connection, authorization, organization_id, client_id, practitioner_id)
        if context['role'] != 'therapist' or not context['can_upload']:
            raise HTTPException(403, 'Only this therapist can upload documents.')
        if not title.strip():
            raise HTTPException(422, 'Enter a document title.')
        body = file.file.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise HTTPException(413, 'Choose a PDF smaller than 20 MB.')
        reader = validate_pdf(body)
        thumbnail = render_page(body, 1)
        document_id = uuid4()
        artifact_id = save_artifact(connection, context, document_id, body, 'original')
        thumbnail_id = save_artifact(connection, context, document_id, thumbnail, 'thumbnail', 'image/png')
        filename = re_safe_filename(file.filename)
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO app.client_documents
                (id, organization_id, client_id, practitioner_id, title, document_type, source_filename,
                 content_artifact_id, uploaded_by_user_id, workflow_status, original_sha256, thumbnail_artifact_id, pdf_page_count)
                VALUES (%s,%s,%s,%s,%s,'other',%s,%s,%s,%s,%s,%s,%s)""",
                (document_id, *scope(context), title.strip(), filename, artifact_id, context['actor_id'],
                 'pending_signature' if request_signature else 'completed', hashlib.sha256(body).hexdigest(), thumbnail_id, len(reader.pages)))
    return {'id': str(document_id)}


def re_safe_filename(filename):
    import re
    name = re.sub(r'[^a-zA-Z0-9._ -]', '_', (filename or 'document.pdf').replace('\\', '/').split('/')[-1])[:160]
    return name if name.lower().endswith('.pdf') else name + '.pdf'


class SignatureRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    consent: bool


@router.post('/clinical-records/clients/{client_id}/documents/{document_id}/sign')
def sign_document(client_id: str, document_id: str, organization_id: str, request: SignatureRequest,
                  practitioner_id: str | None = None, authorization: str | None = Header(default=None)):
    if not request.consent or not request.name.strip():
        raise HTTPException(422, 'Enter your full name and agree to sign electronically.')
    with connect() as connection:
        context = authorize(connection, authorization, organization_id, client_id, practitioner_id)
        if context['role'] != 'client':
            raise HTTPException(403, 'Only the linked client can sign this document.')
        row = document_row(connection, context, document_id, lock=True)
        if row['workflow_status'] != 'pending_signature' or row['signed_artifact_id']:
            raise HTTPException(409, 'This document is no longer awaiting a signature. Refresh the document list.')
        body, _ = read_artifact(connection, context, row['content_artifact_id'])
        digest = hashlib.sha256(body).hexdigest()
        if row['original_sha256'] and digest != row['original_sha256']:
            raise HTTPException(409, 'The original document could not be verified.')
        now = datetime.now(timezone.utc)
        signed = signed_pdf(body, request.name.strip(), now, document_id)
        artifact_id = save_artifact(connection, context, document_id, signed, 'signed')
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE app.client_documents SET signed_artifact_id=%s,
                signer_portal_account_id=%s, signer_name=%s, signature_consent=%s,
                original_sha256=%s, signed_at=%s, completed_at=%s, workflow_status='signed' WHERE id=%s""",
                (artifact_id, context['portal_id'], request.name.strip(), CONSENT, digest, now, now, document_id))
    return {'id': document_id, 'workflowStatus': 'signed'}


@router.get('/clinical-records/clients/{client_id}/documents/{document_id}/{asset}')
def document_asset(client_id: str, document_id: str, asset: str, organization_id: str,
                   practitioner_id: str | None = None, authorization: str | None = Header(default=None)):
    if asset not in ('content', 'signed', 'thumbnail'):
        raise HTTPException(404, 'Document file not found.')
    with connect() as connection:
        context = authorize(connection, authorization, organization_id, client_id, practitioner_id)
        row = document_row(connection, context, document_id)
        artifact_id = row[{'content': 'content_artifact_id', 'signed': 'signed_artifact_id', 'thumbnail': 'thumbnail_artifact_id'}[asset]]
        body, content_type = read_artifact(connection, context, artifact_id)
    filename = ('signed-' if asset == 'signed' else '') + re_safe_filename(row['source_filename'])
    return Response(body, media_type=content_type, headers={'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff', 'Content-Disposition': f'inline; filename="{filename}"'})


@router.get('/clinical-records/clients/{client_id}/documents/{document_id}/pages/{page_number}')
def document_page(client_id: str, document_id: str, page_number: int, organization_id: str,
                  practitioner_id: str | None = None, signed: bool = False,
                  authorization: str | None = Header(default=None)):
    with connect() as connection:
        context = authorize(connection, authorization, organization_id, client_id, practitioner_id)
        row = document_row(connection, context, document_id)
        with connection.cursor() as cursor:
            cursor.execute('SELECT artifact_id FROM app.client_document_pages WHERE document_id=%s AND page_number=%s',
                           (document_id, page_number))
            page = cursor.fetchone()
        if page and not signed:
            body, content_type = read_artifact(connection, context, page['artifact_id'])
        else:
            body, _ = read_artifact(connection, context, row['signed_artifact_id'] if signed else row['content_artifact_id'])
            body, content_type = render_page(body, page_number), 'image/png'
    return Response(body, media_type=content_type, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
