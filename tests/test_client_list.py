import unittest
from unittest.mock import patch
from uuid import uuid4

import server


class ClientListTests(unittest.TestCase):
    def test_workspace_rejects_a_different_client_before_loading_profile(self):
        with patch.object(server, 'current_identity', return_value={'role': 'therapist'}), patch.object(server, 'connect'), patch.object(server, 'resolve_sharing_context', return_value={'client_id': 'linked', 'organization_id': 'org'}):
            with self.assertRaises(server.HTTPException) as error:
                server.relationship_profile('Bearer therapist', client_id='another-client')
            self.assertEqual(error.exception.status_code, 403)

    def test_client_account_is_denied(self):
        with patch.object(server, 'validate_access_token', return_value={'sub': 'client'}), patch.object(server, 'connect') as connect:
            cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = None
            with self.assertRaises(server.HTTPException) as error:
                server.therapist_clients('Bearer client')
            self.assertEqual(error.exception.status_code, 403)
            self.assertEqual(cursor.execute.call_count, 1)

    def test_returns_database_clients_and_empty_list(self):
        row = {'id': uuid4(), 'organization_id': uuid4(), 'name': 'Database Client', 'email': None, 'phone': None, 'status': 'active'}
        for rows in ([], [row]):
            with patch.object(server, 'validate_access_token', return_value={'sub': 'therapist'}), patch.object(server, 'connect') as connect:
                cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
                cursor.fetchone.return_value = {'id': uuid4()}
                cursor.fetchall.return_value = rows
                result = server.therapist_clients('Bearer therapist')['clients']
                self.assertEqual(len(result), len(rows))
                if rows:
                    self.assertEqual(result[0]['id'], str(row['id']))
                    self.assertEqual(result[0]['name'], row['name'])

    def test_invalid_token_never_opens_database(self):
        with patch.object(server, 'validate_access_token', side_effect=server.HTTPException(401)), patch.object(server, 'connect') as connect:
            with self.assertRaises(server.HTTPException):
                server.therapist_clients(None)
            connect.assert_not_called()
