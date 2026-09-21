"""Export active organization IDs for Terraform, or verify/register its output.

Run from the repository root with python -m tools.configure_organization_storage.
This command never creates AWS resources; Terraform owns provisioning.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import UUID

import boto3
from dotenv import load_dotenv

from database.connection import connect

ROOT = Path(__file__).resolve().parents[1]


def register(bindings):
    account = boto3.client('sts').get_caller_identity()['Account']
    # Verify all cloud resources before registering any of them.
    for organization_id, binding in bindings.items():
        UUID(organization_id)
        s3 = boto3.client('s3', region_name=binding['region'])
        bucket = binding['bucket']
        s3.head_bucket(Bucket=bucket, ExpectedBucketOwner=account)
        tags = {item['Key']: item['Value'] for item in s3.get_bucket_tagging(Bucket=bucket)['TagSet']}
        if tags.get('OrganizationId') != organization_id:
            raise RuntimeError('Bucket organization tag does not match the database organization.')
        controls = s3.get_public_access_block(Bucket=bucket)['PublicAccessBlockConfiguration']
        if not all(controls.get(key) for key in ('BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets')):
            raise RuntimeError('Bucket public access protection is incomplete.')
        if s3.get_bucket_versioning(Bucket=bucket).get('Status') != 'Enabled':
            raise RuntimeError('Bucket versioning must be enabled.')
        encryption = s3.get_bucket_encryption(Bucket=bucket)['ServerSideEncryptionConfiguration']['Rules'][0]['ApplyServerSideEncryptionByDefault']
        if encryption.get('SSEAlgorithm') != 'aws:kms' or encryption.get('KMSMasterKeyID') != binding['kms_key_arn']:
            raise RuntimeError('Bucket encryption does not match its registered key.')
    migration = ROOT / 'database/migrations/009_organization_storage.sql'
    digest = hashlib.sha256(migration.read_bytes()).hexdigest()
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('organization-storage-setup',))
        cursor.execute('SELECT checksum FROM app.schema_migrations WHERE name=%s', (migration.name,))
        existing = cursor.fetchone()
        if existing and existing['checksum'] != digest:
            raise RuntimeError('Applied migration checksum differs; create a new migration.')
        if not existing:
            sql = migration.read_text(encoding='utf-8').replace('BEGIN;', '').replace('COMMIT;', '')
            cursor.execute(sql)
            cursor.execute('INSERT INTO app.schema_migrations(name, checksum) VALUES (%s,%s)', (migration.name, digest))
        for organization_id, binding in bindings.items():
            cursor.execute('SELECT * FROM app.organization_storage WHERE organization_id=%s', (organization_id,))
            previous = cursor.fetchone()
            keys = ('bucket', 'region', 'kms_key_arn', 'healthscribe_role_arn')
            if previous:
                if any(previous[key] != binding[key] for key in keys):
                    raise RuntimeError('Changing an existing storage binding requires an explicit data migration.')
                continue
            cursor.execute('INSERT INTO app.organization_storage(organization_id,bucket,region,kms_key_arn,healthscribe_role_arn) VALUES (%s,%s,%s,%s,%s)',
                           (organization_id, *(binding[key] for key in keys)))
    print(f'Verified and registered {len(bindings)} organization bucket(s).')


def main():
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--export-vars', type=Path)
    modes.add_argument('--register-from-terraform', type=Path)
    parser.add_argument('--environment', choices=['demo', 'staging', 'production'])
    args = parser.parse_args()
    if args.export_vars:
        if not args.environment:
            parser.error('--environment is required with --export-vars')
        existing = json.loads(args.export_vars.read_text()) if args.export_vars.exists() else {}
        if existing.get('environment', args.environment) != args.environment:
            raise RuntimeError('Use a separate Terraform state directory for each environment.')
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT id FROM app.organizations WHERE status='active'")
            ids = {str(row['id']) for row in cursor.fetchall()}
        ids.update(existing.get('organization_ids', []))
        existing.update(environment=args.environment, organization_ids=sorted(ids))
        args.export_vars.write_text(json.dumps(existing, indent=2)+'\n', encoding='utf-8')
        print(f'Exported {len(ids)} organization ID(s); existing IDs retained.')
    else:
        result = subprocess.run(['terraform', f'-chdir={args.register_from_terraform.resolve()}', 'output', '-json', 'organization_storage'], check=True, capture_output=True, text=True)
        register(json.loads(result.stdout))


if __name__ == '__main__':
    main()
