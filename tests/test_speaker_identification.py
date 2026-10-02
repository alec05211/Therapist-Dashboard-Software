import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

import server
from database import speaker_identification as identification


class SpeakerIdentificationTests(unittest.TestCase):
    def test_provider_roles_remain_verbatim_until_explicitly_named(self):
        labels = ['PATIENT_0', 'Clinician_0', 'PARENT_0', 'CLINICIAN_1', 'spk_0']
        names = identification.resolve_names(labels, {'PATIENT_0': 'Corrected'},
                                             {'CLINICIAN_0': 'Jeremy'})
        self.assertEqual(names, {'PATIENT_0': 'Corrected', 'Clinician_0': 'Jeremy',
            'PARENT_0': 'PARENT_0', 'CLINICIAN_1': 'CLINICIAN_1', 'spk_0': 'spk_0'})

    def test_provider_labels_are_preserved_and_deduplicated(self):
        names = identification.resolve_names(['PATIENT_1', 'PATIENT_0', 'PATIENT_1'], {})
        self.assertEqual(names, {'PATIENT_1': 'PATIENT_1', 'PATIENT_0': 'PATIENT_0'})

    def test_profile_names_override_account_defaults(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [{'participant_role': 'client', 'display_name': 'Preferred name'}]
        cursor.fetchone.return_value = {'client_name': 'Account name', 'therapist_name': 'Therapist'}
        storage = {'session_id': 'session', 'organization_id': 'org', 'client_id': 'client'}
        self.assertEqual(identification.read_defaults(cursor, storage), {'client': 'Preferred name', 'therapist': 'Therapist'})
        self.assertEqual(cursor.execute.call_args.args[1], ('session', 'org', 'client'))

    def test_discovered_speakers_keep_session_provenance_and_bounded_samples(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [dict(transcript_version_id=uuid4(), runtime_id='session-1',
            session_label='Session 1', audio_key='private/audio.wav', speaker_label='PARENT_0',
            display_label='Reviewed parent', starts_at_seconds=12, ends_at_seconds=22)]
        result = identification.list_associations(cursor, {'organization_id': 'org', 'client_id': 'client'})
        self.assertEqual(result[0]['name'], 'Reviewed parent')
        self.assertEqual(result[0]['sourceLabel'], 'PARENT_0')
        self.assertEqual(result[0]['sample'], {'recordingUrl': '/api/recordings/session-1/audio.wav?client_id=client', 'start': 12.0, 'end': 22.0})
        sql, params = cursor.execute.call_args.args
        self.assertIn('app.transcript_speaker_samples', sql)
        self.assertIn('first_sequence', sql)
        self.assertIn('newer.version_number>transcript.version_number', sql)
        self.assertEqual(params, ('org', 'client'))

    def test_identification_preserves_each_transcripts_provider_labels(self):
        cursor = MagicMock()
        first, second = uuid4(), uuid4()
        cursor.fetchall.return_value = [
            dict(transcript_version_id=first, runtime_id='session-1', session_label='One',
                 audio_key='audio.wav', speaker_label='PATIENT_0', display_label=None,
                 starts_at_seconds=0, ends_at_seconds=2),
            dict(transcript_version_id=first, runtime_id='session-1', session_label='One',
                 audio_key='audio.wav', speaker_label='PATIENT_1', display_label=None,
                 starts_at_seconds=2, ends_at_seconds=4),
            dict(transcript_version_id=second, runtime_id='session-2', session_label='Two',
                 audio_key='audio.wav', speaker_label='CLINICIAN_0', display_label=None,
                 starts_at_seconds=0, ends_at_seconds=2),
        ]
        result = identification.list_associations(cursor, {'organization_id': 'org', 'client_id': 'client'})
        self.assertEqual([row['sourceLabel'] for row in result], ['PATIENT_0', 'PATIENT_1', 'CLINICIAN_0'])

    def test_sample_storage_selects_each_detected_speaker_once(self):
        cursor = MagicMock()
        identification.store_samples(cursor, {
            'organization_id': 'org', 'client_id': 'client', 'session_id': 'session'
        }, 'transcript')
        sql, params = cursor.execute.call_args.args
        self.assertIn('DISTINCT ON (segment.speaker_label)', sql)
        self.assertIn('LEAST(chosen.ends_at_seconds, chosen.starts_at_seconds + 10.000)', sql)
        self.assertIn('ON CONFLICT (transcript_version_id, source_label) DO NOTHING', sql)
        self.assertEqual(params, ('transcript', 'org', 'client', 'session'))

    def test_cross_client_or_stale_speaker_cannot_be_saved(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        association = SimpleNamespace(transcript_version_id=uuid4(), source_label='PARENT_0', name='Name')
        with self.assertRaises(ValueError):
            identification.save_associations(cursor, {'organization_id': 'org', 'client_id': 'client'}, [association], 'actor')
        self.assertEqual(cursor.execute.call_count, 1)
        self.assertEqual(cursor.execute.call_args.args[1][1:], ('org', 'client', 'PARENT_0'))

    def test_clear_removes_relationship_name_and_matching_transcript_names(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {'id': uuid4()}
        association = SimpleNamespace(transcript_version_id=uuid4(), source_label='CLINICIAN_0', name='')
        identification.save_associations(cursor, {'organization_id': 'org', 'client_id': 'client'}, [association], 'actor')
        self.assertIn('DELETE FROM app.transcript_speaker_labels', cursor.execute.call_args.args[0])
        self.assertEqual(cursor.execute.call_args.args[1], ('org', 'client', 'CLINICIAN_0'))

    def test_saved_relationship_name_propagates_to_all_matching_transcripts(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {'id': uuid4()}
        association = SimpleNamespace(transcript_version_id=uuid4(), source_label='patient_1', name=' Marcus ')
        identification.save_associations(cursor, {'organization_id': 'org', 'client_id': 'client'}, [association], 'actor')
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any('app.client_speaker_label_profiles' in sql and 'INSERT INTO' in sql for sql in statements))
        propagation = next(call for call in cursor.execute.call_args_list
                           if 'INSERT INTO app.transcript_speaker_labels' in call.args[0])
        self.assertIn('upper(segment.speaker_label)=%s', propagation.args[0])
        self.assertEqual(propagation.args[1], ('Marcus', 'actor', 'org', 'client', 'PATIENT_1'))

    def test_identification_write_rejects_another_relationship_before_mutation(self):
        request = server.ClientIdentificationRequest(organization_id='other-org', client_id='other-client',
            client={'name': 'Client'}, therapist={'name': 'Therapist'})
        with patch.object(server, 'connect'), patch.object(server, 'resolve_therapist_client_context', return_value={'organization_id': 'org', 'client_id': 'client'}), patch.object(identification, 'save_associations') as save:
            with self.assertRaises(HTTPException) as error:
                server.update_client_identification(request, 'Bearer token')
        self.assertEqual(error.exception.status_code, 403)
        save.assert_not_called()

    def test_identification_accepts_optional_pronouns(self):
        request = server.ParticipantIdentificationRequest(name=' Client ', pronouns=' they/them ')
        self.assertEqual(request.name, 'Client')
        self.assertEqual(request.pronouns, 'they/them')
        self.assertIsNone(server.ParticipantIdentificationRequest(name='Client', pronouns=' ').pronouns)
