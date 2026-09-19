import asyncio
import itertools
import unittest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from starlette.requests import Request
import server


class SharingTests(unittest.TestCase):
    def test_all_permission_combinations_do_not_leak_other_categories(self):
        for flags in itertools.product((False, True), repeat=5):
            permissions = dict(zip(server.PERMISSION_FIELDS, flags))
            connection = MagicMock()
            connection.cursor.return_value.__enter__.return_value.fetchall.return_value = []
            with patch.object(server, 'connect') as connect, patch.object(server, 'resolve_sharing_context', return_value={'organization_id': 'org', 'client_id': 'client'}), patch.object(server, 'read_portal_permissions', return_value=permissions):
                connect.return_value.__enter__.return_value = connection
                result = server.client_portal('Bearer client')
            self.assertEqual('insights' in result, flags[2])
            self.assertEqual('sessions' in result, flags[0] or flags[1] or flags[3])
            for session in result.get('sessions', []):
                self.assertEqual('created_at' in session, flags[0])
                self.assertEqual('segments' in session, flags[1])
                self.assertEqual('draft_note' in session, flags[3])
                self.assertEqual('recording_url' in session, flags[1] and flags[4])
                self.assertNotIn('healthscribe', session)
                self.assertTrue(session['id'].startswith('heartwell-sadic-session-'))
            if 'sessions' in result:
                self.assertEqual(len(result['sessions']), 6)

    def test_audio_requires_both_sharing_permissions_and_bound_session(self):
        for transcript, audio in itertools.product((False, True), repeat=2):
            permissions = dict.fromkeys(server.PERMISSION_FIELDS, False)
            permissions.update(can_view_shared_transcripts=transcript, can_play_shared_recordings=audio)
            with patch.object(server, 'connect'), patch.object(server, 'resolve_sharing_context', return_value={}), patch.object(server, 'read_portal_permissions', return_value=permissions):
                if transcript and audio:
                    response = server.shared_session_recording('heartwell-sadic-session-01', 'Bearer client')
                    self.assertEqual(response.media_type, 'audio/wav')
                    with self.assertRaises(HTTPException) as error:
                        server.shared_session_recording('another-client-session', 'Bearer client')
                    self.assertEqual(error.exception.status_code, 404)
                else:
                    with self.assertRaises(HTTPException) as error:
                        server.shared_session_recording('heartwell-sadic-session-01', 'Bearer client')
                    self.assertEqual(error.exception.status_code, 403)

    def test_relationship_profile_returns_only_database_contact_fields(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = [{'id': 'internal', 'name': 'Database Person', 'email': 'care@example.com', 'phone': None, 'auth0_subject': 'subject'}]
        for role in ('client', 'therapist'):
            with patch.object(server, 'connect') as connect, patch.object(server, 'current_identity', return_value={'role': role}), patch.object(server, 'resolve_sharing_context', return_value={'organization_id': 'o', 'client_id': 'c'}) as resolve:
                connect.return_value.__enter__.return_value = connection
                result = server.relationship_profile('Bearer identity')
                self.assertEqual(result, {'name': 'Database Person', 'email': 'care@example.com', 'phone': None, 'initials': 'DP', 'role': 'Therapist' if role == 'client' else 'Client', 'imageSrc': None, 'aboutMe': None})
                resolve.assert_called_once_with(connection, 'Bearer identity', therapist=role == 'therapist')
                if role == 'client':
                    self.assertIn('practitioner.contact_email', cursor.execute.call_args_list[-2].args[0])
                    self.assertNotIn('actor.email', cursor.execute.call_args_list[-2].args[0])

    def test_ambiguous_relationship_profile_denied(self):
        with patch.object(server, 'connect') as connect, patch.object(server, 'current_identity', return_value={'role': 'client'}), patch.object(server, 'resolve_sharing_context', return_value={'organization_id': 'o', 'client_id': 'c'}):
            cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            for rows in ([], [{}, {}]):
                cursor.fetchall.return_value = rows
                with self.assertRaises(HTTPException) as error:
                    server.relationship_profile('Bearer client')
                self.assertEqual(error.exception.status_code, 403)

    def test_client_cannot_write_about_me(self):
        payload = server.AccountProfileUpdate(name='Elena', email='care@example.com', about_me='Private text')
        with patch.object(server, 'connect'), patch.object(server, 'account_profile_target', return_value=('client', 'subject', {'id': 'client'})):
            with self.assertRaises(HTTPException) as error:
                server.update_account_profile(payload, 'Bearer client')
            self.assertEqual(error.exception.status_code, 403)

    def test_photo_validation_rejects_unsupported_or_oversize_content(self):
        self.assertTrue(server.valid_photo(b'\x89PNG\r\n\x1a\n' + b'content', 'image/png'))
        self.assertFalse(server.valid_photo(b'<svg>not an image</svg>', 'image/png'))
        self.assertFalse(server.valid_photo(b'GIF89a', 'image/gif'))

    def test_missing_permissions_deny_all(self):
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = None
        self.assertFalse(any(server.read_portal_permissions(connection, {'organization_id': 'o', 'client_id': 'c'}).values()))

    def test_unlinked_or_ambiguous_context_denied(self):
        for rows in ([], [{'client_id': 'a'}, {'client_id': 'b'}]):
            connection = MagicMock()
            connection.cursor.return_value.__enter__.return_value.fetchall.return_value = rows
            with patch.object(server, 'validate_access_token', return_value={'sub': 'other'}):
                for therapist in (False, True):
                    with self.assertRaises(HTTPException) as error:
                        server.resolve_sharing_context(connection, 'Bearer other', therapist=therapist)
                    self.assertEqual(error.exception.status_code, 403)

    def test_spoofed_client_write_rejected(self):
        request = server.ClientPortalPermissionsRequest(organization_id='o', client_id='other', **dict.fromkeys(server.PERMISSION_FIELDS, True))
        with patch.object(server, 'connect'), patch.object(server, 'resolve_sharing_context', return_value={'organization_id': 'o', 'client_id': 'linked'}):
            with self.assertRaises(HTTPException) as error:
                server.update_client_portal_permissions(request, 'Bearer therapist')
            self.assertEqual(error.exception.status_code, 403)

    def test_legacy_routes_block_client_before_reading_files(self):
        async def run():
            for path in ('/transcripts', '/transcripts/heartwell-sadic-session-01', '/recordings/session/transcript.json', '/demo/heartwell-sadic/insights', '/transcribe'):
                request = Request({'type': 'http', 'path': path, 'method': 'GET', 'headers': []})
                with patch.object(server, 'connect'), patch.object(server, 'resolve_sharing_context', side_effect=HTTPException(403, 'Denied')):
                    response = await server.protect_legacy_clinical_routes(request, MagicMock(side_effect=AssertionError('Must not reach handler')))
                self.assertEqual(response.status_code, 403)
        asyncio.run(run())

    def test_missing_token_rejected(self):
        with self.assertRaises(HTTPException) as error:
            server.resolve_sharing_context(MagicMock(), None)
        self.assertEqual(error.exception.status_code, 401)


if __name__ == '__main__':
    unittest.main()
