import unittest
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch

from starlette.requests import Request

import server


class ClientDocumentTests(unittest.TestCase):
    def test_document_listing_exposes_application_urls_not_storage_locations(self):
        row = {
            "id": "document-id", "title": "Consent", "document_type": "consent_form",
            "source_filename": "consent.pdf", "version_number": 1,
            "created_at": datetime(2026, 9, 21, tzinfo=timezone.utc),
            "content_type": "application/pdf", "byte_size": 1234, "has_thumbnail": True,
            "workflow_status": "draft", "page_count": 3,
        }
        with patch.object(server, "connect"), patch.object(server, "authorize_clinical_access"), \
                patch.object(server.client_documents, "list_documents", return_value=[row]):
            result = server.get_client_documents("client-id", "organization-id", "Bearer therapist")
        document = result["documents"][0]
        self.assertEqual(document["title"], "Consent")
        self.assertIn("/api/clinical-records/clients/client-id/documents/document-id/content", document["contentUrl"])
        self.assertIn("/thumbnail", document["thumbnailUrl"])
        self.assertEqual(document["workflowStatus"], "draft")
        self.assertEqual(len(document["pageUrls"]), 3)
        self.assertIn("/pages/1", document["pageUrls"][0])
        self.assertNotIn("storage_bucket", document)
        self.assertNotIn("object_key", document)

    def test_document_content_is_read_from_version_pinned_s3_object(self):
        artifact = {
            "storage_bucket": "private-bucket", "object_key": "clients/c/documents/d/consent.pdf",
            "object_version_id": "version-1", "content_type": "application/pdf", "byte_size": 3,
            "source_filename": "consent.pdf", "region": "us-east-1",
        }
        s3 = MagicMock()
        s3.get_object.return_value = {"Body": BytesIO(b"pdf"), "ContentLength": 3, "AcceptRanges": "bytes"}
        request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
        with patch.object(server, "connect"), patch.object(server, "authorize_clinical_access"), \
                patch.object(server.client_documents, "get_document_artifact", return_value=artifact), \
                patch.object(server.boto3, "client", return_value=s3):
            response = server.get_client_document_asset(
                "client-id", "document-id", "content", "organization-id", request, "Bearer therapist")
        self.assertEqual(response.body, b"pdf")
        self.assertEqual(response.media_type, "application/pdf")
        s3.get_object.assert_called_once_with(Bucket="private-bucket", Key=artifact["object_key"], VersionId="version-1")

    def test_document_page_is_read_from_its_version_pinned_s3_object(self):
        artifact = {
            "storage_bucket": "private-bucket", "object_key": "clients/c/documents/d/pages/page-2.png",
            "object_version_id": "page-version", "content_type": "image/png", "byte_size": 3,
            "source_filename": "consent.pdf", "region": "us-east-1",
        }
        s3 = MagicMock()
        s3.get_object.return_value = {"Body": BytesIO(b"png"), "ContentLength": 3, "AcceptRanges": "bytes"}
        request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
        with patch.object(server, "connect"), patch.object(server, "authorize_clinical_access"), \
                patch.object(server.client_documents, "get_document_page_artifact", return_value=artifact), \
                patch.object(server.boto3, "client", return_value=s3):
            response = server.get_client_document_page(
                "client-id", "document-id", 2, "organization-id", request, "Bearer therapist")
        self.assertEqual(response.body, b"png")
        self.assertEqual(response.media_type, "image/png")
        s3.get_object.assert_called_once_with(Bucket="private-bucket", Key=artifact["object_key"], VersionId="page-version")


if __name__ == "__main__":
    unittest.main()
