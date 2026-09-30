import unittest
from unittest.mock import patch
from uuid import uuid4

import server


class ClientRegistrationTests(unittest.TestCase):
    def test_normalizes_client_names(self):
        request = server.ClientOnboardingRequest(
            first_name="  Marcus  ", last_name=" Reynolds ",
            email="MARCUS@example.com", discoverable=True,
        )
        self.assertEqual(request.first_name, "Marcus")
        self.assertEqual(request.last_name, "Reynolds")
        self.assertEqual(request.email, "marcus@example.com")

    def test_registers_an_unconnected_client_identity(self):
        registration_id = uuid4()
        with patch.object(server, "validate_access_token", return_value={"sub": "auth0|marcus"}), patch.object(server, "connect") as connect:
            cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.side_effect = [None, None, {"id": registration_id}]

            result = server.onboard_client(server.ClientOnboardingRequest(
                first_name="Marcus", last_name="Reynolds",
                email="marcus@example.com", discoverable=True,
            ), "Bearer token")

        self.assertTrue(result["created"])
        self.assertFalse(result["connected"])
        self.assertEqual(result["name"], "Marcus Reynolds")
        self.assertEqual(result["registration_id"], str(registration_id))

    def test_inviting_registration_does_not_create_scoped_client(self):
        registration_id, invitation_id, organization_id = uuid4(), uuid4(), uuid4()
        principal = {"organization_id": organization_id, "practitioner_id": uuid4(), "actor_user_id": uuid4()}
        registration = {"id": registration_id, "first_name": "Marcus", "last_name": "Reynolds", "email": "marcus@example.com"}
        with patch.object(server, "therapist_principal", return_value=principal), patch.object(server, "connect") as connect:
            cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.side_effect = [registration, None, {"id": invitation_id}]

            result = server.invite_registered_client(registration_id, "Bearer therapist")

        self.assertEqual(result["invitation"]["id"], str(invitation_id))
        self.assertEqual(result["invitation"]["name"], "Marcus Reynolds")
        self.assertEqual(cursor.execute.call_count, 3)

    def test_directory_registration_uses_account_profile_photo(self):
        registration_id = uuid4()
        principal = {"organization_id": uuid4(), "practitioner_id": uuid4(), "actor_user_id": uuid4()}
        with patch.object(server, "therapist_principal", return_value=principal), patch.object(server, "connect") as connect:
            cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchall.return_value = [{
                "id": registration_id, "kind": "registration", "name": "Marcus Reynolds",
                "email": "marcus@example.com", "phone": None, "has_photo": True,
                "relationship": "available",
            }]

            result = server.therapist_client_directory("Marcus", "Bearer therapist")

        self.assertEqual(
            result["clients"][0]["photoUrl"],
            f"/api/therapist/client-directory/{registration_id}/photo",
        )
        self.assertIn("profile.photo IS NOT NULL", cursor.execute.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
