import hashlib
import unittest
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException, UploadFile
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from database import document_workflow as workflow

ORG, CLIENT, PRACTITIONER, DOCUMENT = [str(uuid4()) for _ in range(4)]
CONTEXT = dict(organization_id=ORG, client_id=CLIENT, practitioner_id=PRACTITIONER,
               role='therapist', can_upload=True, actor_id=str(uuid4()), portal_id=None)


def pdf():
    output = BytesIO()
    page = canvas.Canvas(output)
    page.drawString(72, 720, 'Document for client review')
    page.save()
    return output.getvalue()


class DocumentAccessTests(unittest.TestCase):
    def test_relationship_is_resolved_from_verified_identity(self):
        with patch.object(workflow, 'validate_access_token', return_value={'sub': 'verified'}), \
                patch.object(workflow, 'relationships', return_value=[CONTEXT]) as rows:
            result = workflow.authorize(MagicMock(), 'Bearer token', ORG, CLIENT)
        self.assertEqual(result, CONTEXT)
        self.assertEqual(rows.call_args.args[1], 'verified')

    def test_other_client_organization_and_practitioner_are_denied(self):
        for org, client, practitioner in [(str(uuid4()), CLIENT, PRACTITIONER),
                (ORG, str(uuid4()), PRACTITIONER), (ORG, CLIENT, str(uuid4()))]:
            with self.subTest(org=org, client=client, practitioner=practitioner), \
                    patch.object(workflow, 'validate_access_token', return_value={'sub': 'verified'}), \
                    patch.object(workflow, 'relationships', return_value=[CONTEXT]):
                with self.assertRaises(HTTPException) as error:
                    workflow.authorize(MagicMock(), 'Bearer token', org, client, practitioner)
                self.assertEqual(error.exception.status_code, 403)

    def test_ambiguous_relationship_fails_closed(self):
        other = {**CONTEXT, 'practitioner_id': str(uuid4())}
        with patch.object(workflow, 'validate_access_token', return_value={'sub': 'verified'}), \
                patch.object(workflow, 'relationships', return_value=[CONTEXT, other]):
            with self.assertRaises(HTTPException):
                workflow.authorize(MagicMock(), 'Bearer token', ORG, CLIENT)
            self.assertEqual(workflow.authorize(MagicMock(), 'Bearer token', ORG, CLIENT, PRACTITIONER), CONTEXT)

    def test_revoked_relationship_has_no_access(self):
        with patch.object(workflow, 'validate_access_token', return_value={'sub': 'verified'}), \
                patch.object(workflow, 'relationships', return_value=[]):
            with self.assertRaises(HTTPException):
                workflow.authorize(MagicMock(), 'Bearer token', ORG, CLIENT)

    def test_document_lookup_scopes_all_three_identifiers_and_locks(self):
        connection = MagicMock()
        workflow.document_row(connection, CONTEXT, DOCUMENT, lock=True)
        query, parameters = connection.cursor.return_value.__enter__.return_value.execute.call_args.args
        self.assertIn('practitioner_id=%s', query)
        self.assertIn('FOR UPDATE', query)
        self.assertEqual(parameters, (ORG, CLIENT, PRACTITIONER, DOCUMENT))

    def test_missing_document_returns_404(self):
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = None
        with self.assertRaises(HTTPException) as error:
            workflow.document_row(connection, CONTEXT, DOCUMENT)
        self.assertEqual(error.exception.status_code, 404)


class DocumentWorkflowTests(unittest.TestCase):
    def test_page_preview_renders_png_and_rejects_out_of_range(self):
        original = pdf()
        self.assertTrue(workflow.render_page(original, 1).startswith(b'\x89PNG'))
        for number in (0, 2):
            with self.assertRaises(HTTPException) as error:
                workflow.render_page(original, number)
            self.assertEqual(error.exception.status_code, 404)

    def test_valid_pdf_and_signature_preserve_original_pages(self):
        original = pdf()
        signed_at = datetime(2026, 9, 22, tzinfo=timezone.utc)
        signed = workflow.signed_pdf(original, 'Elena Example', signed_at, DOCUMENT)
        reader = PdfReader(BytesIO(signed))
        self.assertEqual(len(reader.pages), 2)
        self.assertIn('Document for client review', reader.pages[0].extract_text())
        receipt = reader.pages[1].extract_text()
        for expected in ['Elena Example', DOCUMENT, hashlib.sha256(original).hexdigest(), '2026-09-22', workflow.CONSENT]:
            self.assertIn(expected, receipt.replace('\n', ' '))
        self.assertEqual(len(PdfReader(BytesIO(original)).pages), 1)

    def test_invalid_encrypted_empty_and_active_pdfs_are_rejected(self):
        encrypted = BytesIO()
        writer = PdfWriter(); writer.add_blank_page(width=100, height=100); writer.encrypt('secret'); writer.write(encrypted)
        active = BytesIO()
        writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
        writer.add_js('app.alert(1)'); writer.write(active)
        empty = BytesIO(); PdfWriter().write(empty)
        for body in [b'not a pdf', encrypted.getvalue(), active.getvalue(), empty.getvalue()]:
            with self.subTest(body=body[:12]), self.assertRaises(HTTPException) as error:
                workflow.validate_pdf(body)
            self.assertEqual(error.exception.status_code, 422)

    def test_only_therapist_with_write_permission_can_upload(self):
        for context in [{**CONTEXT, 'role': 'client'}, {**CONTEXT, 'can_upload': False}]:
            with patch.object(workflow, 'connect'), patch.object(workflow, 'authorize', return_value=context), \
                    patch.object(workflow, 'save_artifact') as save:
                with self.assertRaises(HTTPException) as error:
                    workflow.upload_document(CLIENT, ORG, UploadFile(BytesIO(pdf()), filename='test.pdf'), 'Title', False)
                self.assertEqual(error.exception.status_code, 403)
                save.assert_not_called()

    def test_upload_stores_original_with_relationship_and_pending_status(self):
        original = pdf()
        with patch.object(workflow, 'connect') as connection, patch.object(workflow, 'authorize', return_value=CONTEXT), \
                patch.object(workflow, 'save_artifact', return_value='artifact') as save:
            result = workflow.upload_document(CLIENT, ORG, UploadFile(BytesIO(original), filename='../consent.pdf'), 'Consent', True)
        self.assertEqual(save.call_count, 2)
        self.assertEqual(save.call_args_list[0].args[3], original)
        params = connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value.execute.call_args.args[1]
        self.assertEqual(params[1:4], (ORG, CLIENT, PRACTITIONER))
        self.assertIn('pending_signature', params)
        self.assertIn('consent.pdf', params)
        self.assertIn('id', result)

    def test_oversize_upload_never_reaches_storage(self):
        with patch.object(workflow, 'connect'), patch.object(workflow, 'authorize', return_value=CONTEXT), \
                patch.object(workflow, 'MAX_BYTES', 10), patch.object(workflow, 'save_artifact') as save:
            with self.assertRaises(HTTPException) as error:
                workflow.upload_document(CLIENT, ORG, UploadFile(BytesIO(b'x' * 11), filename='large.pdf'), 'Title', False)
            self.assertEqual(error.exception.status_code, 413)
            save.assert_not_called()

    def test_therapist_cannot_sign_for_client(self):
        with patch.object(workflow, 'connect'), patch.object(workflow, 'authorize', return_value=CONTEXT):
            with self.assertRaises(HTTPException) as error:
                workflow.sign_document(CLIENT, DOCUMENT, ORG, workflow.SignatureRequest(name='Elena', consent=True))
            self.assertEqual(error.exception.status_code, 403)

    def test_signature_requires_consent_and_nonblank_name(self):
        for request in [workflow.SignatureRequest(name='Elena', consent=False), workflow.SignatureRequest(name=' ', consent=True)]:
            with self.assertRaises(HTTPException) as error:
                workflow.sign_document(CLIENT, DOCUMENT, ORG, request)
            self.assertEqual(error.exception.status_code, 422)

    def test_repeat_signature_is_rejected_without_writing_storage(self):
        with patch.object(workflow, 'connect'), patch.object(workflow, 'authorize', return_value={**CONTEXT, 'role': 'client'}), \
                patch.object(workflow, 'document_row', return_value={'workflow_status': 'signed', 'signed_artifact_id': 'existing'}), \
                patch.object(workflow, 'save_artifact') as save:
            with self.assertRaises(HTTPException) as error:
                workflow.sign_document(CLIENT, DOCUMENT, ORG, workflow.SignatureRequest(name='Elena', consent=True))
            self.assertEqual(error.exception.status_code, 409)
            save.assert_not_called()

    def test_signature_saves_separate_artifact_and_server_identity(self):
        original = pdf()
        context = {**CONTEXT, 'role': 'client', 'portal_id': 'verified-client'}
        row = dict(workflow_status='pending_signature', signed_artifact_id=None, content_artifact_id='original', original_sha256=hashlib.sha256(original).hexdigest())
        with patch.object(workflow, 'connect') as connection, patch.object(workflow, 'authorize', return_value=context), \
                patch.object(workflow, 'document_row', return_value=row) as lookup, \
                patch.object(workflow, 'read_artifact', return_value=(original, 'application/pdf')), \
                patch.object(workflow, 'save_artifact', return_value='signed') as save:
            workflow.sign_document(CLIENT, DOCUMENT, ORG, workflow.SignatureRequest(name='Elena', consent=True))
        self.assertTrue(lookup.call_args.kwargs['lock'])
        self.assertEqual(save.call_args.args[4], 'signed')
        query, params = connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value.execute.call_args.args
        self.assertNotIn('SET content_artifact_id', query)
        self.assertEqual(params[:4], ('signed', 'verified-client', 'Elena', workflow.CONSENT))

    def test_asset_reads_version_pinned_object(self):
        connection, s3 = MagicMock(), MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = dict(
            storage_bucket='private', object_key='relationship/document.pdf', object_version_id='version-1', region='us-east-1', content_type='application/pdf')
        s3.get_object.return_value = {'Body': BytesIO(b'pdf')}
        with patch.object(workflow.boto3, 'client', return_value=s3):
            body, content_type = workflow.read_artifact(connection, CONTEXT, 'artifact')
        self.assertEqual(body, b'pdf')
        self.assertEqual(content_type, 'application/pdf')
        s3.get_object.assert_called_once_with(Bucket='private', Key='relationship/document.pdf', VersionId='version-1')


class DocumentHttpTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, method, path, body=b'', content_type='application/json'):
        app = FastAPI()
        app.include_router(workflow.router)
        messages = []

        async def receive():
            return {'type': 'http.request', 'body': body, 'more_body': False}

        async def send(message):
            messages.append(message)

        await app({'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                   'method': method, 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
                   'query_string': f'organization_id={ORG}&practitioner_id={PRACTITIONER}'.encode(),
                   'headers': [(b'content-type', content_type.encode()), (b'authorization', b'Bearer test')],
                   'server': ('test', 80), 'client': ('test', 123), 'root_path': ''}, receive, send)
        status = next(message['status'] for message in messages if message['type'] == 'http.response.start')
        payload = b''.join(message.get('body', b'') for message in messages if message['type'] == 'http.response.body')
        return status, payload

    async def test_multipart_upload_reaches_authorized_storage_workflow(self):
        body = (b'--test\r\nContent-Disposition: form-data; name="title"\r\n\r\nAgreement\r\n'
                b'--test\r\nContent-Disposition: form-data; name="request_signature"\r\n\r\ntrue\r\n'
                b'--test\r\nContent-Disposition: form-data; name="file"; filename="agreement.pdf"\r\n'
                b'Content-Type: application/pdf\r\n\r\n' + pdf() + b'\r\n--test--\r\n')
        with patch.object(workflow, 'connect'), patch.object(workflow, 'authorize', return_value=CONTEXT), \
                patch.object(workflow, 'save_artifact', return_value=str(uuid4())) as save:
            status, payload = await self.request('POST', f'/clinical-records/clients/{CLIENT}/documents', body,
                                                 'multipart/form-data; boundary=test')
        self.assertEqual(status, 201, payload)
        self.assertEqual(save.call_count, 2)

    async def test_storage_failure_returns_safe_retryable_error(self):
        with patch.object(workflow, 'connect', side_effect=RuntimeError('private internal detail')):
            status, payload = await self.request('GET', f'/clinical-records/clients/{CLIENT}/documents')
        self.assertEqual(status, 503)
        self.assertNotIn(b'private internal detail', payload)

    async def test_signed_asset_denies_wrong_relationship_before_read(self):
        with patch.object(workflow, 'connect'), \
                patch.object(workflow, 'authorize', side_effect=HTTPException(403, 'Denied')), \
                patch.object(workflow, 'read_artifact') as read:
            status, _ = await self.request('GET', f'/clinical-records/clients/{CLIENT}/documents/{DOCUMENT}/signed')
        self.assertEqual(status, 403)
        read.assert_not_called()

    async def test_missing_signature_consent_returns_validation_error(self):
        status, _ = await self.request('POST', f'/clinical-records/clients/{CLIENT}/documents/{DOCUMENT}/sign', b'{"name":"Elena"}')
        self.assertEqual(status, 422)


if __name__ == '__main__':
    unittest.main()
