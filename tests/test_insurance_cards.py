import io
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from ai_harness import insurance_card as analyzer
from database import insurance_cards


ORG, CLIENT, CARD = [uuid4() for _ in range(3)]
CONTEXT = {"organization_id": ORG, "client_id": CLIENT, "actor_user_id": None, "subject": "auth0|client"}
FIELDS = {key: None for key in analyzer.INSURANCE_FIELD_KEYS}
FIELDS.update({"payer_name": "Example Health", "member_id": "ABC123"})
PNG = b"\x89PNG\r\n\x1a\n" + b"image"


class InsuranceAnalyzerTests(unittest.TestCase):
    def test_images_are_stateless_and_structured(self):
        with patch.object(analyzer, "_request_structured_response", return_value=(FIELDS, {"id": "resp-1", "model": "vision-model"})) as request:
            fields, metadata = analyzer.extract_insurance_card(
                front=PNG, front_content_type="image/png", back=PNG, back_content_type="image/png",
                api_key="secret", model="vision-model",
            )
        payload = request.call_args.args[0]
        self.assertFalse(payload["store"])
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertEqual(len([item for item in payload["input"][0]["content"] if item["type"] == "input_image"]), 2)
        self.assertEqual(fields["member_id"], "ABC123")
        self.assertEqual(metadata["response_id"], "resp-1")


class InsuranceWorkflowTests(unittest.TestCase):
    def test_only_a_single_active_client_identity_is_authorized(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []
        with patch.object(insurance_cards, "validate_access_token", return_value={"sub": "auth0|therapist"}):
            with self.assertRaises(HTTPException) as error:
                insurance_cards._client_context(connection, "Bearer token")
        self.assertEqual(error.exception.status_code, 403)

    def test_therapist_insurance_access_requires_an_active_relationship(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []
        with patch.object(insurance_cards, "validate_access_token", return_value={"sub": "auth0|therapist"}):
            with self.assertRaises(HTTPException) as error:
                insurance_cards._therapist_context(connection, "Bearer token", str(CLIENT))
        self.assertEqual(error.exception.status_code, 403)
        self.assertIn("access.can_read_clinical", cursor.execute.call_args.args[0])

    def test_therapist_response_exposes_only_effective_administrative_fields(self):
        now = datetime.now(timezone.utc)
        row = {
            "id": CARD, "status": "ready", "front_filename": "front.png", "back_filename": "back.png",
            "model_extracted_fields": FIELDS, "client_corrected_fields": {**FIELDS, "member_id": "CORRECTED"},
            "source_model": "vision-model", "source_response_id": "resp", "updated_at": now,
        }
        response = insurance_cards._therapist_card_response(row)["card"]
        self.assertEqual(response["fields"]["member_id"], "CORRECTED")
        self.assertTrue(response["clientReviewed"])
        self.assertNotIn("frontFilename", response)
        self.assertNotIn("model", response)
        self.assertNotIn("sourceResponseId", response)

    def test_therapist_view_is_audited(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        row = {
            "id": CARD, "status": "ready", "model_extracted_fields": FIELDS,
            "client_corrected_fields": None, "updated_at": datetime.now(timezone.utc),
        }
        context = {"organization_id": ORG, "client_id": CLIENT, "actor_user_id": uuid4()}
        with patch.object(insurance_cards, "connect", return_value=connection), \
                patch.object(insurance_cards, "_therapist_context", return_value=context), \
                patch.object(insurance_cards, "_active_card", return_value=row), \
                patch.object(insurance_cards, "_audit") as audit:
            result = insurance_cards.get_client_insurance_card(str(CLIENT), "Bearer token")
        self.assertEqual(result["card"]["fields"]["payer_name"], "Example Health")
        audit.assert_called_once_with(connection, context, "insurance_card.view", CARD)

    def test_model_extraction_and_client_correction_are_separate(self):
        now = datetime.now(timezone.utc)
        row = {
            "id": CARD, "status": "ready", "front_filename": "front.png", "back_filename": "back.png",
            "model_extracted_fields": FIELDS, "client_corrected_fields": {**FIELDS, "member_id": "CORRECTED"},
            "source_model": "vision-model", "analyzed_at": now, "updated_at": now,
        }
        response = insurance_cards._card_response(row)["card"]
        self.assertEqual(response["fields"]["member_id"], "CORRECTED")
        self.assertEqual(response["source"], "client")
        self.assertEqual(row["model_extracted_fields"]["member_id"], "ABC123")

    def test_rejects_disguised_or_oversized_images(self):
        for body, mime in [(b"not-an-image", "image/png"), (PNG, "application/pdf")]:
            with self.subTest(mime=mime), self.assertRaises(HTTPException):
                insurance_cards._read_image(UploadFile(io.BytesIO(body), filename="card.png", headers={"content-type": mime}))

    def test_upload_uses_kms_and_persists_structured_result(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            {"bucket": "private", "region": "us-east-1", "kms_key_arn": "key"},
            {"id": uuid4()}, {"id": uuid4()},
        ]
        ready = {
            "id": CARD, "status": "ready", "front_filename": "front.png", "back_filename": "back.png",
            "model_extracted_fields": FIELDS, "client_corrected_fields": None, "source_model": "vision-model",
            "analyzed_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        }
        second_connection = MagicMock()
        second_connection.__enter__.return_value = second_connection
        second_cursor = second_connection.cursor.return_value.__enter__.return_value
        second_cursor.fetchone.return_value = ready
        aws = MagicMock(); aws.put_object.return_value = {"VersionId": "v1"}
        front = UploadFile(io.BytesIO(PNG), filename="front.png", headers={"content-type": "image/png"})
        back = UploadFile(io.BytesIO(PNG), filename="back.png", headers={"content-type": "image/png"})
        with patch.dict(os.environ, {"OPENAI_API_KEY": "configured", "INSURANCE_CARD_MODEL": "vision-model", "INSURANCE_CARD_OPENAI_APPROVED": "true"}), \
                patch.object(insurance_cards, "connect", side_effect=[connection, second_connection]), \
                patch.object(insurance_cards, "_client_context", return_value=CONTEXT), \
                patch.object(insurance_cards.boto3, "client", return_value=aws), \
                patch.object(insurance_cards, "extract_insurance_card", return_value=(FIELDS, {"provider": "openai", "model": "vision-model", "response_id": "resp"})), \
                patch.object(insurance_cards, "_audit"):
            operation = insurance_cards.upload_insurance_card(front, back, "Bearer token")
            try:
                operation.send(None)
            except StopIteration as completed:
                result = completed.value
            else:
                self.fail("The upload coroutine unexpectedly yielded.")
        self.assertEqual(aws.put_object.call_count, 2)
        self.assertTrue(all(call.kwargs["ServerSideEncryption"] == "aws:kms" for call in aws.put_object.call_args_list))
        self.assertEqual(result["card"]["fields"]["payer_name"], "Example Health")

    def test_edit_writes_corrections_without_updating_model_fields(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor = connection.cursor.return_value.__enter__.return_value
        card = {"id": CARD, "status": "ready"}
        corrected = {
            "id": CARD, "status": "ready", "front_filename": "front.png", "back_filename": "back.png",
            "model_extracted_fields": FIELDS, "client_corrected_fields": {**FIELDS, "member_id": "CORRECTED"},
            "source_model": "vision-model", "analyzed_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        }
        cursor.fetchone.return_value = corrected
        with patch.object(insurance_cards, "connect", return_value=connection), \
                patch.object(insurance_cards, "_client_context", return_value=CONTEXT), \
                patch.object(insurance_cards, "_active_card", return_value=card), \
                patch.object(insurance_cards, "_audit"):
            insurance_cards.update_insurance_fields(insurance_cards.InsuranceFieldsUpdate(fields={**FIELDS, "member_id": "CORRECTED"}), "Bearer token")
        sql = cursor.execute.call_args.args[0]
        self.assertIn("client_corrected_fields", sql)
        self.assertNotIn("model_extracted_fields", sql)


if __name__ == "__main__":
    unittest.main()
