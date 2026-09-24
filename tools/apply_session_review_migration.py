"""Apply additive clinical-workspace migrations with local TLS settings."""

import hashlib
from pathlib import Path

from dotenv import load_dotenv

from database.connection import connect


ROOT = Path(__file__).resolve().parents[1]


def main():
    load_dotenv(ROOT / '.env')
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('session-review-migration',))
        for name in ('010_transcript_speaker_labels.sql', '011_client_journey_entries.sql', '012_client_identification.sql', '013_account_pronouns.sql', '014_client_documents.sql', '015_client_document_workflow.sql', '016_relationship_documents.sql'):
            migration = ROOT / 'database/migrations' / name
            digest = hashlib.sha256(migration.read_bytes()).hexdigest()
            cursor.execute('SELECT checksum FROM app.schema_migrations WHERE name=%s', (migration.name,))
            existing = cursor.fetchone()
            if existing:
                if existing['checksum'] != digest:
                    raise RuntimeError('Applied migration checksum differs; create a new migration.')
                print(f'Already applied: {migration.name}')
                continue
            cursor.execute(migration.read_text(encoding='utf-8').replace('BEGIN;', '').replace('COMMIT;', ''))
            cursor.execute('INSERT INTO app.schema_migrations(name, checksum) VALUES (%s,%s)', (migration.name, digest))
            print(f'Applied: {migration.name}')


if __name__ == '__main__':
    main()
