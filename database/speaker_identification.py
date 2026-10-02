"""Names and review samples; source labels are not biometric identities."""

from pathlib import Path


def store_samples(cursor, storage, transcript_version_id):
    """Persist one stable, bounded source-audio pointer per diarized speaker."""
    cursor.execute("""INSERT INTO app.transcript_speaker_samples
        (transcript_version_id, source_label, transcript_segment_id, audio_artifact_id,
         starts_at_seconds, ends_at_seconds)
        SELECT chosen.transcript_version_id, chosen.speaker_label, chosen.id, audio.id,
               chosen.starts_at_seconds,
               LEAST(chosen.ends_at_seconds, chosen.starts_at_seconds + 10.000)
        FROM (
          SELECT DISTINCT ON (segment.speaker_label)
                 segment.id, segment.transcript_version_id, segment.speaker_label,
                 segment.starts_at_seconds, segment.ends_at_seconds, segment.sequence_number
          FROM app.transcript_segments segment
          WHERE segment.transcript_version_id=%s
            AND segment.speaker_label IS NOT NULL
            AND length(trim(segment.speaker_label)) > 0
            AND segment.ends_at_seconds > segment.starts_at_seconds
          ORDER BY segment.speaker_label,
                   (segment.ends_at_seconds-segment.starts_at_seconds) DESC,
                   segment.sequence_number
        ) chosen
        JOIN LATERAL (
          SELECT artifact.id
          FROM app.clinical_artifacts artifact
          WHERE artifact.organization_id=%s AND artifact.client_id=%s
            AND artifact.session_id=%s AND artifact.artifact_type='audio_recording'
            AND artifact.lifecycle_state='active' AND artifact.deleted_at IS NULL
          ORDER BY artifact.created_at DESC LIMIT 1
        ) audio ON true
        ON CONFLICT (transcript_version_id, source_label) DO NOTHING""",
        (transcript_version_id, storage['organization_id'], storage['client_id'], storage['session_id']))


def resolve_names(labels, overrides, relationship_names=None):
    """Return reviewed names or the provider's exact diarization labels.

    HealthScribe's PATIENT/CLINICIAN values are job-local model output, not
    durable identities. Preserve them verbatim until the therapist explicitly
    associates that label with a name in this care relationship.
    """
    names = dict(overrides)
    relationship_names = {key.upper(): value for key, value in (relationship_names or {}).items()}
    for label in dict.fromkeys(labels):
        if label not in names:
            names[label] = relationship_names.get(label.upper(), label)
    return names


def read_relationship_names(cursor, context):
    cursor.execute("""SELECT source_label, display_name
        FROM app.client_speaker_label_profiles
        WHERE organization_id=%s AND client_id=%s""",
        (context['organization_id'], context['client_id']))
    return {row['source_label']: row['display_name'] for row in cursor.fetchall()}


def read_defaults(cursor, storage):
    cursor.execute("""SELECT profile.participant_role, profile.display_name
        FROM app.client_identification_profiles profile
        WHERE profile.organization_id=%s AND profile.client_id=%s""",
        (storage['organization_id'], storage['client_id']))
    saved = {row['participant_role']: row['display_name'] for row in cursor.fetchall()}
    cursor.execute("""SELECT client.display_name AS client_name,
            (SELECT min(practitioner.professional_name)
             FROM app.session_practitioner_participants participant
             JOIN app.organization_practitioners practitioner ON practitioner.id=participant.practitioner_id
               AND practitioner.organization_id=session.organization_id
             WHERE participant.session_id=session.id AND participant.participation_role='therapist'
             HAVING count(DISTINCT practitioner.id)=1) AS therapist_name
        FROM app.sessions session
        JOIN app.clients client ON client.id=session.client_id AND client.organization_id=session.organization_id
        WHERE session.id=%s AND session.organization_id=%s AND session.client_id=%s""",
        (storage['session_id'], storage['organization_id'], storage['client_id']))
    row = cursor.fetchone() or {}
    return {'client': saved.get('client') or row.get('client_name'),
            'therapist': saved.get('therapist') or row.get('therapist_name')}


def list_associations(cursor, context):
    cursor.execute("""SELECT transcript.id AS transcript_version_id, job.runtime_id,
            COALESCE(job.storage->>'label', 'Completed session') AS session_label,
            job.storage->>'audio_key' AS audio_key, segment.speaker_label,
            COALESCE(label.display_label, profile.display_name) AS display_label,
            sample.starts_at_seconds, sample.ends_at_seconds,
            (SELECT min(first_segment.sequence_number)
             FROM app.transcript_segments first_segment
             WHERE first_segment.transcript_version_id=transcript.id
               AND first_segment.speaker_label=segment.speaker_label) AS first_sequence
        FROM app.session_storage_jobs job
        JOIN app.transcript_versions transcript ON transcript.session_id=job.session_id
          AND transcript.organization_id=job.organization_id AND transcript.client_id=job.client_id
        JOIN app.transcript_speaker_samples sample ON sample.transcript_version_id=transcript.id
        JOIN app.transcript_segments segment ON segment.id=sample.transcript_segment_id
        LEFT JOIN app.transcript_speaker_labels label ON label.transcript_version_id=transcript.id
          AND label.source_label=segment.speaker_label
        LEFT JOIN app.client_speaker_label_profiles profile
          ON profile.organization_id=transcript.organization_id AND profile.client_id=transcript.client_id
          AND profile.source_label=upper(segment.speaker_label)
        WHERE job.organization_id=%s AND job.client_id=%s AND job.status='COMPLETED'
          AND transcript.status <> 'superseded' AND segment.speaker_label IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM app.transcript_versions newer
            WHERE newer.session_id=transcript.session_id AND newer.version_number>transcript.version_number
              AND newer.status <> 'superseded')
        ORDER BY transcript.id, first_sequence, segment.speaker_label""",
        (context['organization_id'], context['client_id']))
    result = []
    for row in cursor.fetchall():
        label = row['speaker_label']
        overrides = {label: row['display_label']} if row['display_label'] else {}
        start = float(row['starts_at_seconds'])
        end = float(row['ends_at_seconds'])
        sample = {'recordingUrl': f"/api/recordings/{row['runtime_id']}/{Path(row['audio_key']).name}?client_id={context['client_id']}",
                  'start': start, 'end': end} if row['audio_key'] and end > start else None
        result.append({'transcriptVersionId': str(row['transcript_version_id']),
                       'sessionId': row['runtime_id'], 'sessionLabel': row['session_label'],
                       'sourceLabel': label,
                       'name': overrides.get(label, ''),
                       'sample': sample, 'overridden': bool(overrides)})
    return result


def save_associations(cursor, context, associations, actor):
    names = {}
    for association in associations:
        cursor.execute("""SELECT transcript.id FROM app.transcript_versions transcript
            JOIN app.transcript_segments segment ON segment.transcript_version_id=transcript.id
            WHERE transcript.id=%s AND transcript.organization_id=%s AND transcript.client_id=%s
              AND segment.speaker_label=%s AND transcript.status <> 'superseded'
              AND NOT EXISTS (SELECT 1 FROM app.transcript_versions newer
                WHERE newer.session_id=transcript.session_id AND newer.version_number>transcript.version_number
                  AND newer.status <> 'superseded') LIMIT 1 FOR UPDATE OF transcript""",
            (association.transcript_version_id, context['organization_id'], context['client_id'], association.source_label))
        if not cursor.fetchone():
            raise ValueError('Speaker association is no longer available for this client. Reload identification settings.')
        source_label = association.source_label.upper()
        name = association.name.strip()
        if source_label in names and names[source_label] != name:
            raise ValueError('The same speaker label has conflicting names. Reload identification settings.')
        names[source_label] = name

    for source_label, name in names.items():
        if not name:
            cursor.execute("""DELETE FROM app.client_speaker_label_profiles
                WHERE organization_id=%s AND client_id=%s AND source_label=%s""",
                (context['organization_id'], context['client_id'], source_label))
            cursor.execute("""DELETE FROM app.transcript_speaker_labels label
                USING app.transcript_versions transcript
                WHERE label.transcript_version_id=transcript.id
                  AND transcript.organization_id=%s AND transcript.client_id=%s
                  AND upper(label.source_label)=%s""",
                (context['organization_id'], context['client_id'], source_label))
        else:
            cursor.execute("""INSERT INTO app.client_speaker_label_profiles
                (organization_id, client_id, source_label, display_name, updated_by_user_id)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT (client_id, source_label)
                DO UPDATE SET organization_id=EXCLUDED.organization_id,
                  display_name=EXCLUDED.display_name,
                  updated_by_user_id=EXCLUDED.updated_by_user_id,
                  updated_at=CURRENT_TIMESTAMP""",
                (context['organization_id'], context['client_id'], source_label, name, actor))
            cursor.execute("""INSERT INTO app.transcript_speaker_labels
                (transcript_version_id, source_label, display_label, updated_by_user_id)
                SELECT DISTINCT transcript.id, segment.speaker_label, %s, %s
                FROM app.transcript_versions transcript
                JOIN app.transcript_segments segment ON segment.transcript_version_id=transcript.id
                WHERE transcript.organization_id=%s AND transcript.client_id=%s
                  AND upper(segment.speaker_label)=%s AND transcript.status <> 'superseded'
                ON CONFLICT (transcript_version_id, source_label)
                DO UPDATE SET display_label=EXCLUDED.display_label,
                  updated_by_user_id=EXCLUDED.updated_by_user_id,
                  updated_at=CURRENT_TIMESTAMP""",
                (name, actor, context['organization_id'], context['client_id'], source_label))
