import json
import os
import unittest
from unittest.mock import MagicMock, patch

from database.connection import database_url_from_local_aws_secret


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


if __name__ == "__main__":
    unittest.main()
