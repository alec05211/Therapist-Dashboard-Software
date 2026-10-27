import json
import os
import unittest
from unittest.mock import MagicMock, patch

from database.connection import database_url_from_local_aws_secret
from database import connection as database
import psycopg


class LocalDatabaseCredentialTests(unittest.TestCase):
    def setUp(self):
        database_url_from_local_aws_secret.cache_clear()

    def tearDown(self):
        database_url_from_local_aws_secret.cache_clear()

    def test_resolved_secret_is_reused_for_process_lifetime(self):
        secrets_manager = MagicMock()
        secrets_manager.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {"username": "local-user", "password": "local-password", "host": "db.example", "dbname": "dashboard"}
            )
        }

        with patch.dict(
            os.environ,
            {"DATABASE_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:demo", "AWS_REGION": "us-east-1"},
            clear=False,
        ), patch("database.connection.boto3.client", return_value=secrets_manager) as client, patch(
            "database.connection.rds_ca_bundle_path", return_value="C:/temp/rds-ca.pem"
        ):
            first = database_url_from_local_aws_secret()
            second = database_url_from_local_aws_secret()

        self.assertEqual(first, second)
        client.assert_called_once_with("secretsmanager", region_name="us-east-1")
        secrets_manager.get_secret_value.assert_called_once()


class ManagedCredentialRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.previous_refresh = database._last_credential_refresh_at
        database._last_credential_refresh_at = None
        self.old_url = 'postgresql://old@db.example/dashboard?sslmode=verify-full'
        self.new_url = 'postgresql://new@db.example/dashboard?sslmode=verify-full'

    def tearDown(self):
        database._last_credential_refresh_at = self.previous_refresh

    def test_password_rejection_refreshes_cached_secret_and_retries_connection_once(self):
        result = MagicMock()
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(database, 'database_url_from_local_aws_secret', side_effect=[self.old_url, self.old_url, self.new_url]) as resolve, \
                patch.object(database.psycopg, 'connect', side_effect=[psycopg.OperationalError('password authentication failed'), result]) as connect:
            self.assertIs(database.connect(), result)
        resolve.cache_clear.assert_called_once()
        self.assertEqual([call.args[0] for call in connect.call_args_list], [self.old_url, self.new_url])

    def test_network_failure_never_refreshes_credentials(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(database, 'database_url_from_local_aws_secret', return_value=self.old_url) as resolve, \
                patch.object(database.psycopg, 'connect', side_effect=psycopg.OperationalError('connection timed out')) as connect:
            with self.assertRaises(psycopg.OperationalError):
                database.connect()
        resolve.cache_clear.assert_not_called()
        connect.assert_called_once()

    def test_explicit_database_url_never_falls_back_to_a_managed_secret(self):
        with patch.dict(os.environ, {'DATABASE_URL': self.old_url}, clear=True), \
                patch.object(database, 'database_url_from_local_aws_secret') as resolve, \
                patch.object(database.psycopg, 'connect', side_effect=psycopg.OperationalError('password authentication failed')) as connect:
            with self.assertRaises(psycopg.OperationalError):
                database.connect()
        resolve.assert_not_called()
        connect.assert_called_once()

    def test_second_password_rejection_does_not_retry_again(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(database, 'database_url_from_local_aws_secret', side_effect=[self.old_url, self.old_url, self.new_url]) as resolve, \
                patch.object(database.psycopg, 'connect', side_effect=psycopg.OperationalError('password authentication failed')) as connect:
            with self.assertRaises(psycopg.OperationalError):
                database.connect()
        self.assertEqual(connect.call_count, 2)
        resolve.cache_clear.assert_called_once()

    def test_refresh_cooldown_bounds_secret_lookups_when_password_stays_rejected(self):
        database._last_credential_refresh_at = 100.0
        with patch.object(database.time, 'monotonic', return_value=110.0), \
                patch.object(database, 'database_url_from_local_aws_secret', return_value=self.old_url) as resolve:
            self.assertIsNone(database._refresh_rejected_managed_credential(self.old_url))
        resolve.cache_clear.assert_not_called()

    def test_concurrent_refresh_reuses_new_cached_credential(self):
        with patch.object(database, 'database_url_from_local_aws_secret', return_value=self.new_url) as resolve:
            self.assertEqual(database._refresh_rejected_managed_credential(self.old_url), self.new_url)
        resolve.cache_clear.assert_not_called()


if __name__ == "__main__":
    unittest.main()
