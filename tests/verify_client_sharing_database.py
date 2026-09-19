"""Live synthetic database verification. All permission changes are rolled back."""
from contextlib import contextmanager
from unittest.mock import patch
from psycopg import Rollback
from database.connection import connect
import server

with connect() as connection:
    with connection.cursor() as cursor:
        cursor.execute("""SELECT portal.auth0_subject AS client_subject, actor.auth0_subject AS therapist_subject
            FROM app.client_portal_accounts portal
            JOIN app.client_therapist_access access ON access.client_id=portal.client_id
            JOIN app.organization_practitioners practitioner ON practitioner.id=access.practitioner_id
            JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id
            JOIN app.application_users actor ON actor.id=membership.user_id
            WHERE portal.synthetic_case_key='heartwell-sadic' AND access.revoked_at IS NULL""")
        identities = cursor.fetchall()
    assert len(identities) == 1, 'Expected exactly one linked synthetic relationship'
    identities = identities[0]
    @contextmanager
    def existing_connection():
        yield connection
    with connection.transaction():
        with patch.object(server, 'connect', existing_connection), patch.object(server, 'validate_access_token', side_effect=lambda token: {'sub': identities['therapist_subject' if token == 'therapist' else 'client_subject']}):
            context = server.get_client_portal_permissions('therapist')
            clients = server.therapist_clients('therapist')['clients']
            assert any(client['id'] == context['client_id'] for client in clients)
            try:
                server.therapist_clients('client')
                raise AssertionError('Client accessed therapist client list')
            except server.HTTPException as error:
                assert error.status_code == 403
            for token, expected_role in [('therapist', 'Client'), ('client', 'Therapist')]:
                profile = server.relationship_profile(token)
                assert profile['role'] == expected_role
                assert 'email' in profile and 'phone' in profile
            with connection.cursor() as cursor:
                cursor.execute('UPDATE app.clients SET email=%s, phone=%s WHERE id=%s', ('updated@example.com', '(555) 010-1000', context['client_id']))
            profile = server.relationship_profile('therapist')
            assert profile['email'] == 'updated@example.com' and profile['phone'] == '(555) 010-1000'

            for enabled in (False, True, False):
                payload = {**context, **dict.fromkeys(server.PERMISSION_FIELDS, enabled)}
                saved = server.update_client_portal_permissions(server.ClientPortalPermissionsRequest(**payload), 'therapist')
                assert all(saved[key] == enabled for key in server.PERMISSION_FIELDS)
                assert server.get_client_portal_permissions('therapist') == saved
                portal = server.client_portal('client')
                assert all(portal['permissions'][key] == enabled for key in server.PERMISSION_FIELDS)
                assert ('sessions' in portal) == enabled
            try:
                server.get_client_portal_permissions('client')
                raise AssertionError('Client accessed therapist settings')
            except server.HTTPException as error:
                assert error.status_code == 403
            with connection.cursor() as cursor:
                cursor.execute('UPDATE app.client_therapist_access SET revoked_at=CURRENT_TIMESTAMP WHERE client_id=%s', (context['client_id'],))
            assert all(client['id'] != context['client_id'] for client in server.therapist_clients('therapist')['clients'])
            try:
                server.get_client_portal_permissions('therapist')
                raise AssertionError('Revoked relationship remained accessible')
            except server.HTTPException as error:
                assert error.status_code == 403
        raise Rollback()
    connection.rollback()
print('Live database: save/reload, portal filtering, client role rejection, and relationship revocation passed; changes rolled back.')
