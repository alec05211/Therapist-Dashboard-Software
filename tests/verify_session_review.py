"""Live synthetic PostgreSQL review roundtrip; all writes are rolled back."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from dotenv import load_dotenv
from psycopg import Rollback

from database.connection import connect
from database import client_journey, organization_storage, session_review
from ai_harness.brief_projection import project_accepted_insights


load_dotenv(Path(__file__).resolve().parents[1] / '.env')

with connect() as connection:
    @contextmanager
    def existing_connection():
        yield connection

    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute("""SELECT client.organization_id, client.id AS client_id, actor.auth0_subject
                FROM app.clients client
                JOIN app.client_portal_accounts portal ON portal.client_id=client.id
                JOIN app.client_therapist_access access ON access.client_id=client.id AND access.organization_id=client.organization_id
                JOIN app.organization_practitioners practitioner ON practitioner.id=access.practitioner_id
                JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id
                JOIN app.application_users actor ON actor.id=membership.user_id
                WHERE portal.synthetic_case_key='heartwell-sadic' AND access.revoked_at IS NULL""")
            actor = cursor.fetchone()
            assert actor, 'Synthetic case is unavailable.'
        context = {key: str(actor[key]) for key in ('organization_id', 'client_id')}
        with patch.object(organization_storage, 'connect', existing_connection), patch.object(session_review, 'connect', existing_connection):
            storage = organization_storage.create_upload(context, '.wav', actor['auth0_subject'])
            with connection.cursor() as cursor:
                cursor.execute("""INSERT INTO app.clinical_artifacts
                    (organization_id, client_id, session_id, artifact_type, source,
                     storage_bucket, object_key, content_type)
                    VALUES (%s,%s,%s,'raw_transcript','healthscribe',%s,%s,'application/json') RETURNING id""",
                    (storage['organization_id'], storage['client_id'], storage['session_id'], storage['bucket'],
                     f"{storage['prefix']}transcripts/synthetic-{uuid4()}.json"))
                source_id = cursor.fetchone()['id']
            segments = [{'start': 0.125, 'end': 1.75, 'speaker': 'PATIENT', 'text': 'A synthetic test statement.'},
                        {'start': 1.8, 'end': 2.5, 'speaker': 'CLINICIAN', 'text': 'A synthetic reply.'}]
            draft = [{'name': 'History', 'items': ['Synthetic draft for verification.']}]
            source_segment_id = str(uuid4())
            raw_transcript = {'Conversation': {'TranscriptSegments': [
                {'SegmentId': source_segment_id, 'Content': segments[0]['text']},
                {'SegmentId': str(uuid4()), 'Content': segments[1]['text']} ]}}
            raw_note = {'ClinicalDocumentation': {'Sections': [
                {'SectionName': 'HISTORY_OF_PRESENT_ILLNESS', 'Summary': [
                    {'SummarizedSegment': 'Synthetic draft for verification.',
                     'EvidenceLinks': [{'SegmentId': source_segment_id}]}]}]}}
            session_review.persist_result(storage, segments, draft, source_id, raw_transcript, raw_note)
            session_review.persist_result(storage, segments, draft, source_id)
            with connection.cursor() as cursor:
                cursor.execute('SELECT count(*) AS count FROM app.transcript_versions WHERE session_id=%s', (storage['session_id'],))
                assert cursor.fetchone()['count'] == 1, 'Retry created a duplicate transcript.'
                cursor.execute('SELECT status FROM app.session_storage_jobs WHERE session_id=%s', (storage['session_id'],))
                assert cursor.fetchone()['status'] == 'COMPLETED'
                cursor.execute('SELECT status FROM app.sessions WHERE id=%s', (storage['session_id'],))
                assert cursor.fetchone()['status'] == 'review'
            result = session_review.read_result(storage)
            assert [part['text'] for part in result['segments']] == [part['text'] for part in segments]
            assert result['clinical_note'] == draft
            assert result['segments'][0]['speaker'] == 'PATIENT'
            assert session_review.save_speaker_labels(storage, {'PATIENT': 'Client'}, actor['auth0_subject']) == {'PATIENT': 'Client'}
            assert session_review.read_result(storage)['speakers'] == {'PATIENT': 'Client'}
            assert session_review.read_result({**storage, 'client_id': str(uuid4())}) is None
            proposals = client_journey.list_entries(connection, storage['organization_id'], storage['client_id'])
            assert len(proposals) == 1 and proposals[0]['status'] == 'proposed'
            assert proposals[0]['evidence'][0]['segment_index'] == 0
            assert client_journey.list_entries(connection, storage['organization_id'], str(uuid4())) == []
            with connection.cursor() as cursor:
                cursor.execute('SELECT id FROM app.application_users WHERE auth0_subject=%s', (actor['auth0_subject'],))
                actor_id = str(cursor.fetchone()['id'])
            assert client_journey.review_entry(connection, organization_id=storage['organization_id'],
                                               client_id=storage['client_id'], entry_id=proposals[0]['id'],
                                               category='theme', content=proposals[0]['text'], state='accepted',
                                               actor_user_id=actor_id)
            assert not client_journey.review_entry(connection, organization_id=storage['organization_id'],
                                                   client_id=str(uuid4()), entry_id=proposals[0]['id'],
                                                   category='theme', content=proposals[0]['text'], state='accepted',
                                                   actor_user_id=actor_id)
            accepted = client_journey.list_entries(connection, storage['organization_id'], storage['client_id'], status='accepted')
            assert len(accepted) == 1
            assert project_accepted_insights(None, accepted)['sections'][0]['items'][0]['text'] == proposals[0]['text']
            client_journey.review_entry(connection, organization_id=storage['organization_id'],
                                        client_id=storage['client_id'], entry_id=proposals[0]['id'],
                                        category='theme', content=proposals[0]['text'], state='stale',
                                        actor_user_id=actor_id)
            assert client_journey.list_entries(connection, storage['organization_id'], storage['client_id'], status='accepted') == []
        raise Rollback()

print('Live session review verified: passages, draft, source-linked journey proposal, therapist acceptance, stale exclusion, retry safety and client scope; all synthetic writes rolled back.')
