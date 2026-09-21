import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from ai_harness.brief_projection import project_accepted_insights
from database import client_journey


class ClientJourneyTests(unittest.TestCase):
    def test_proposal_requires_matching_healthscribe_evidence(self):
        cursor = MagicMock()
        segment_id = uuid4()
        proposal_id = uuid4()
        cursor.fetchall.return_value = [{'id': segment_id, 'sequence_number': 0}]
        cursor.fetchone.return_value = {'id': proposal_id}
        raw_transcript = {'Conversation': {'TranscriptSegments': [
            {'Content': 'Skipped empty speech', 'SegmentId': 'source-a'},
            {'Content': '', 'SegmentId': 'empty'},
            {'Content': 'Real source.', 'SegmentId': 'source-b'},
        ]}}
        raw_note = {'ClinicalDocumentation': {'Sections': [{'SectionName': 'HISTORY', 'Summary': [
            {'SummarizedSegment': 'Grounded proposal.', 'EvidenceLinks': [{'SegmentId': 'source-a'}]},
            {'SummarizedSegment': 'Unsupported proposal.', 'EvidenceLinks': [{'SegmentId': 'missing'}]},
        ]}]}}
        storage = {key: str(uuid4()) for key in ('organization_id', 'client_id', 'session_id')}
        written = client_journey.propose_from_healthscribe(cursor, storage, raw_transcript, raw_note, uuid4())
        self.assertEqual(written, 1)
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertEqual(sum('INSERT INTO app.client_journey_entries' in sql for sql in statements), 1)
        evidence_call = next(call for call in cursor.execute.call_args_list if 'INSERT INTO app.client_journey_evidence' in call.args[0])
        self.assertEqual(evidence_call.args[1], (proposal_id, segment_id))

    def test_review_scopes_update_and_records_revision(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'status': 'proposed', 'category': 'context', 'content': 'Original'}
        entry_id, client_id, organization_id, actor_id = [str(uuid4()) for _ in range(4)]
        self.assertTrue(client_journey.review_entry(connection, organization_id=organization_id, client_id=client_id,
                                                    entry_id=entry_id, category='theme', content='Reviewed',
                                                    state='accepted', actor_user_id=actor_id))
        scope_call = cursor.execute.call_args_list[0]
        self.assertIn('FOR UPDATE', scope_call.args[0])
        self.assertEqual(scope_call.args[1], (entry_id, organization_id, client_id))
        self.assertTrue(any('INSERT INTO app.client_journey_entry_revisions' in call.args[0]
                            for call in cursor.execute.call_args_list))

    def test_only_accepted_entries_can_reach_bounded_brief(self):
        evidence = [{'evidence_id': str(uuid4()), 'session_id': f'session-{uuid4()}',
                     'session_label': 'Completed session', 'segment_index': 0,
                     'start': 0, 'end': 1, 'quote': 'Synthetic source'}]
        entries = [{'status': 'accepted', 'category': 'open_thread', 'text': f'Accepted {index}', 'evidence': evidence}
                   for index in range(12)]
        entries.insert(0, {'status': 'proposed', 'category': 'theme', 'text': 'Unapproved', 'evidence': evidence})
        brief = project_accepted_insights(None, entries)
        self.assertEqual(sum(len(section['items']) for section in brief['sections']), 8)
        self.assertNotIn('Unapproved', str(brief))
