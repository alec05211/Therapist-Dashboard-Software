import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from database.clinical_context import build_clinical_context, fingerprint
from ai_harness.journey_proposals import discover_openai_evidence_claims
from ai_harness.longitudinal_insights import generate_openai_longitudinal_insights
from database.clinical_synthesis_worker import _generate_bundle
from database.longitudinal_records import InsightEvidence, InsightItem, LongitudinalRecordRepository
from ai_harness.brief_projection import project_accepted_insights
from ai_harness.clinical_context import MAX_CONTEXT_BYTES, synthesis_context


class ClinicalContextTests(unittest.TestCase):
    def build(self, entries=(), notes=(), snapshot=None):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = notes
        with patch('database.clinical_context.client_journey.list_entries', return_value=entries), \
                patch('database.clinical_context.LongitudinalRecordRepository') as repository:
            repository.return_value.get_latest_insight_snapshot.return_value = snapshot
            packet = build_clinical_context(connection, organization_id='org', client_id='client',
                                            exclude_session_id='new')
            repository.return_value.get_latest_insight_snapshot.assert_called_once_with(
                organization_id='org', client_id='client')
        self.assertEqual(cursor.execute.call_args.args[1], ('org', 'client'))
        self.assertIn("note.status='finalized'", cursor.execute.call_args.args[0])
        return packet

    def entry(self, state, session='old'):
        return dict(id=state+session, session_id='session-'+session, text=state+' claim',
                    status=state, categories=['context'], evidence=[dict(
                        evidence_id=state+session, session_id='session-'+session,
                        session_label='Old session', quote='Client statement')])

    def test_states_remain_distinct_and_same_session_proposals_are_excluded(self):
        packet = self.build([self.entry(s) for s in
                             ['accepted', 'proposed', 'rejected', 'hidden', 'stale', 'disputed']]
                            + [self.entry('proposed', 'new')])
        self.assertEqual([s['evidence_id'] for s in packet['source_evidence']], ['acceptedold'])
        self.assertEqual(len(packet['pending_proposals']), 1)
        self.assertEqual(len(packet['review_constraints']), 4)
        self.assertEqual(packet['clinician_decisions'][0]['status'], 'accepted')
        self.assertFalse(packet['coverage']['snapshot_available'])

    def test_finalized_note_is_citable_without_an_accepted_transcript_claim(self):
        packet = self.build(notes=[dict(id='note', session_id='old', version_number=2,
            content={'plain_text': 'Clinician amendment'}, finalized_at=datetime.now(timezone.utc),
            session_label='Old session')])
        source = packet['source_evidence'][0]
        self.assertEqual(source['source_type'], 'finalized_clinical_note')
        self.assertEqual(source['clinical_note_version_id'], 'note')
        self.assertNotIn('transcript_segment_id', source)
        changed = {**packet, 'pending_proposals': [{'status': 'proposed'}]}
        self.assertNotEqual(fingerprint(packet), fingerprint(changed))

    def test_prior_interpretations_remain_labeled_and_hidden_items_are_constraints(self):
        packet = self.build(snapshot={'id': 'snapshot', 'version': 3, 'items': [
            dict(id='visible', review_state='draft', kind='theme', content={'analysis': 'Maybe'}),
            dict(id='hidden', review_state='hidden', kind='theme', content={'analysis': 'Suppressed'}),
        ]})
        self.assertEqual(packet['generated_interpretations'][0]['review_state'], 'draft')
        self.assertEqual(packet['review_constraints'][0]['id'], 'hidden')
        self.assertNotIn('Suppressed', json.dumps(packet))

    def test_discovery_gets_shared_context_but_can_only_cite_new_transcript(self):
        packet = self.build([self.entry('proposed')])
        with patch('ai_harness.journey_proposals._request_structured_response',
                   return_value=({'claims': []}, {})) as request:
            discover_openai_evidence_claims(segments=[dict(segment_key='new', text='New grief topic')],
                                           insights_context=packet, api_key='test', model='test')
        payload = request.call_args.args[0]
        self.assertEqual(json.loads(payload['input'])['clinical_context'], packet)
        self.assertIn('never a relevance gate', payload['instructions'])
        schema = payload['text']['format']['schema']
        self.assertEqual(schema['properties']['claims']['items']['properties']
                         ['evidence_segment_keys']['items']['enum'], ['new'])

    def test_synthesis_and_repairs_keep_shared_context(self):
        packet = self.build([self.entry('proposed')])
        with patch('ai_harness.longitudinal_insights._request_structured_response',
                   return_value=({'overview': 'test', 'items': []}, {})) as request:
            with self.assertRaises(RuntimeError):
                generate_openai_longitudinal_insights(evidence=[{'evidence_id': 'accepted'}],
                    clinical_context=packet, api_key='test', model='test', kind='theme')
        self.assertEqual(request.call_count, 4)
        for call in request.call_args_list:
            self.assertEqual(json.loads(call.args[0]['input'])['clinical_context'],
                             synthesis_context(packet, [{'evidence_id': 'accepted'}]))

    def test_novel_topic_can_be_discovered_without_matching_an_existing_interpretation(self):
        packet = self.build(snapshot={'id': 'snapshot', 'version': 1, 'items': [
            dict(id='work', review_state='draft', kind='theme', content={'analysis': 'Work stress'})]})
        claim = dict(claim_summary='Client discussed grief', evidence_segment_keys=['0'],
                     categories=['context'], synthesis_focus='Preserve the newly discussed grief',
                     relationship='novel', related_insight_item_ids=[])
        with patch('ai_harness.journey_proposals._request_structured_response',
                   return_value=({'claims': [claim]}, {})):
            claims, _ = discover_openai_evidence_claims(
                segments=[dict(segment_key='0', text='I want to discuss grief today')],
                insights_context=packet, api_key='test', model='test')
        self.assertEqual(claims[0]['claim_summary'], 'Client discussed grief')
        self.assertEqual(claims[0]['related_insight_item_ids'], [])

    def test_oversized_context_fails_before_provider_submission(self):
        entry = self.entry('proposed')
        entry['text'] = 'x' * (MAX_CONTEXT_BYTES + 1)
        with self.assertRaisesRegex(ValueError, 'bounded input'):
            self.build([entry])

    def test_larger_finalized_note_preserves_complete_text_and_lineage(self):
        text = 'x' * 140_000
        packet = self.build(notes=[dict(id='note', session_id='old', version_number=2,
            content={'plain_text': text}, finalized_at=datetime.now(timezone.utc),
            session_label='Old session')])
        self.assertEqual(packet['source_evidence'][0]['content']['plain_text'], text)
        self.assertEqual(packet['source_evidence'][0]['clinical_note_version_id'], 'note')

    def test_repeated_sources_become_references_without_losing_unique_pending_evidence(self):
        accepted = self.entry('accepted')
        shared = self.entry('proposed')
        shared['evidence'] = accepted['evidence']
        unique = self.entry('proposed', 'another')
        unique['evidence'][0]['quote'] = 'Unique unreviewed quotation'
        packet = self.build([accepted, shared, unique], snapshot={'items': [dict(
            id='prior', kind='theme', review_state='draft', content={'analysis': 'Tentative'},
            evidence=[dict(transcript_segment_id='acceptedold', session_id='old',
                           quote='Client statement', note_text='Repeated note body')])]})
        self.assertEqual(packet['pending_proposals'][0]['evidence_refs'][0]['evidence_id'], 'acceptedold')
        self.assertNotIn('evidence', packet['pending_proposals'][0])
        self.assertEqual(packet['pending_proposals'][1]['evidence'][0]['quote'], 'Unique unreviewed quotation')
        prior = packet['generated_interpretations'][0]
        self.assertEqual(prior['content']['analysis'], 'Tentative')
        self.assertEqual(prior['evidence_refs'][0]['transcript_segment_id'], 'acceptedold')
        self.assertNotIn('Repeated note body', json.dumps(packet))
        self.assertEqual(packet['source_evidence'][0]['quote'], 'Client statement')

    def test_synthesis_sends_source_bodies_once_on_initial_and_repair_calls(self):
        evidence = [{'evidence_id': 'source', 'quote': 'UNIQUE_SOURCE_BODY'}]
        packet = {**self.build(), 'source_evidence': evidence}
        with patch('ai_harness.longitudinal_insights._request_structured_response',
                   return_value=({'overview': 'test', 'items': []}, {})) as request:
            with self.assertRaises(RuntimeError):
                generate_openai_longitudinal_insights(evidence=evidence,
                    clinical_context=packet, api_key='test', model='test')
        self.assertEqual(request.call_count, 4)
        for call in request.call_args_list:
            payload_input = json.loads(call.args[0]['input'])
            self.assertEqual(call.args[0]['input'].count('UNIQUE_SOURCE_BODY'), 1)
            self.assertEqual(payload_input['clinical_context']['source_evidence_ids'], ['source'])
            self.assertNotIn('source_evidence', payload_input['clinical_context'])
        self.assertEqual(packet['source_evidence'], evidence)

    def test_request_above_previous_cap_reaches_provider_and_new_cap_still_rejects(self):
        evidence = [{'evidence_id': 'source', 'quote': 'x' * 200_000}]
        with patch('ai_harness.longitudinal_insights._request_structured_response',
                   side_effect=RuntimeError('provider reached')) as request:
            with self.assertRaisesRegex(RuntimeError, 'provider reached'):
                generate_openai_longitudinal_insights(evidence=evidence,
                    clinical_context={'source_evidence': evidence}, api_key='test', model='test')
            request.assert_called_once()
        evidence[0]['quote'] = 'x' * 350_001
        with patch('ai_harness.longitudinal_insights._request_structured_response') as request:
            with self.assertRaisesRegex(RuntimeError, 'bounded input'):
                generate_openai_longitudinal_insights(evidence=evidence,
                    clinical_context=None, api_key='test', model='test')
            request.assert_not_called()

    def test_oversized_repair_still_fails_before_resubmission(self):
        with patch('ai_harness.longitudinal_insights._request_structured_response',
                   return_value=({'overview': 'x' * 350_001, 'items': []}, {})) as request:
            with self.assertRaisesRegex(RuntimeError, 'repair request exceeds the bounded input'):
                generate_openai_longitudinal_insights(evidence=[{'evidence_id': 'source'}],
                    clinical_context=None, api_key='test', model='test')
            request.assert_called_once()

    def test_direct_contradiction_can_be_preserved_as_a_new_proposal(self):
        packet = self.build(snapshot={'id': 'snapshot', 'version': 1, 'items': [
            dict(id='work', review_state='draft', kind='theme', content={'analysis': 'Work stress'})]})
        claim = dict(claim_summary='Client says work is no longer the main concern',
                     evidence_segment_keys=['0'], categories=['context'],
                     synthesis_focus='Preserve the change from the earlier work focus',
                     relationship='contrasts', related_insight_item_ids=['work'])
        with patch('ai_harness.journey_proposals._request_structured_response',
                   return_value=({'claims': [claim]}, {})):
            claims, _ = discover_openai_evidence_claims(
                segments=[dict(segment_key='0', text='Work is no longer my main concern')],
                insights_context=packet, api_key='test', model='test')
        self.assertEqual(claims[0]['relationship'], 'contrasts')
        self.assertEqual(claims[0]['evidence_segment_keys'], ['0'])

    def test_curated_context_is_a_clinician_decision_not_a_generated_interpretation(self):
        packet = self.build(snapshot={'items': [dict(id='curated', kind='therapist_curated',
            review_state='accepted', content={'text': 'Review priority'}, evidence=[])]})
        self.assertEqual(packet['clinician_decisions'][0]['origin'], 'clinician_curated')
        self.assertEqual(packet['generated_interpretations'], [])

    def test_note_lineage_survives_insights_to_brief_projection(self):
        note = dict(evidence_id='note', clinical_note_version_id='note',
                    source_type='finalized_clinical_note', session_id='session-old',
                    session_label='Old session', content={'plain_text': 'Finalized observation'})
        def insight(**kwargs):
            return {'overview': 'Review', 'items': [dict(kind='open_thread', label='Review',
                analysis='Review this observation', analysis_claims=[dict(phrase='this observation',
                    occurrence=0, evidence_ids=['E001'])], context_statements=[])]}, {'model': 'test'}
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test'}), \
                patch('database.clinical_synthesis_worker.resolve_brief', return_value={}), \
                patch('database.clinical_synthesis_worker.brief_input', return_value=(None, {'evidence': []})):
            generator = MagicMock(side_effect=insight)
            context = {'source_evidence': [note], 'generated_interpretations': [
                {'evidence_refs': [{'clinical_note_version_id': 'note'}]}]}
            bundle = _generate_bundle([note], clinical_context=context, insights_model='test', brief_model='test',
                insight_generator=generator, brief_generator=lambda **kwargs: ({}, {}))
        generator.assert_called_once()
        self.assertNotIn('kind', generator.call_args.kwargs)
        self.assertEqual(generator.call_args.kwargs['clinical_context']['generated_interpretations'][0]
                         ['evidence_refs'][0]['clinical_note_version_id'], 'E001')
        self.assertEqual(context['source_evidence'][0]['evidence_id'], 'note')
        self.assertEqual(bundle['generated_items'][0]['content']['analysis_claims'][0]['evidence_ids'], ['note'])
        source = bundle['packet']['items'][0]['evidence'][0]
        self.assertEqual(source['clinical_note_version_id'], 'note')
        self.assertIsNone(source['transcript_segment_id'])
        self.assertEqual(source['note_text'], 'Finalized observation')
        item = bundle['generated_items'][0]
        InsightItem(item_kind=item['kind'], content=item['content'],
                    evidence=(InsightEvidence(clinical_note_version_id='note'),)).validate()
        projected = project_accepted_insights(bundle['packet'])
        projected_source = projected['sections'][0]['items'][0]['sources'][0]
        self.assertEqual(projected_source['clinical_note_version_id'], 'note')
        self.assertNotIn('segment_index', projected_source)

    def test_persisted_note_citation_resolves_exact_version_content_and_session(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = dict(id='snapshot', version_number=1, status='accepted',
            generator_name='test', generator_version='test', selection_policy_version='test',
            content={}, created_at=datetime.now(timezone.utc), reviewed_at=None)
        cursor.fetchall.return_value = [dict(id='item', item_kind='theme', review_state='draft',
            display_order=0, content={}, evidence_role='supporting', transcript_segment_id=None,
            clinical_note_version_id='note-v2', session_id='old', session_label='Old session',
            note_content={'plain_text': 'Exact finalized revision'}, note_version_number=2)]
        packet = LongitudinalRecordRepository(connection).get_latest_insight_snapshot(
            organization_id='org', client_id='client')
        source = packet['items'][0]['evidence'][0]
        self.assertEqual(source['session_id'], 'old')
        self.assertEqual(source['note_text'], 'Exact finalized revision')
        self.assertEqual(source['note_version_number'], 2)


if __name__ == '__main__':
    unittest.main()
