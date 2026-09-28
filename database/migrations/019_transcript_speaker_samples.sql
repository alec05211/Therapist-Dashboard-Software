BEGIN;

CREATE TABLE app.transcript_speaker_samples (
  transcript_version_id uuid NOT NULL REFERENCES app.transcript_versions(id) ON DELETE CASCADE,
  source_label text NOT NULL,
  transcript_segment_id uuid NOT NULL REFERENCES app.transcript_segments(id) ON DELETE CASCADE,
  audio_artifact_id uuid NOT NULL REFERENCES app.clinical_artifacts(id),
  starts_at_seconds numeric(12, 3) NOT NULL CHECK (starts_at_seconds >= 0),
  ends_at_seconds numeric(12, 3) NOT NULL CHECK (ends_at_seconds > starts_at_seconds),
  review_status text NOT NULL DEFAULT 'unverified'
    CHECK (review_status IN ('unverified', 'confirmed', 'rejected')),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_at timestamptz,
  reviewed_by_user_id uuid REFERENCES app.application_users(id),
  PRIMARY KEY (transcript_version_id, source_label),
  CHECK (length(trim(source_label)) > 0),
  CHECK (ends_at_seconds - starts_at_seconds <= 10.000)
);

INSERT INTO app.transcript_speaker_samples
  (transcript_version_id, source_label, transcript_segment_id, audio_artifact_id,
   starts_at_seconds, ends_at_seconds)
SELECT chosen.transcript_version_id, chosen.speaker_label, chosen.id, audio.id,
       chosen.starts_at_seconds,
       LEAST(chosen.ends_at_seconds, chosen.starts_at_seconds + 10.000)
FROM (
  SELECT DISTINCT ON (segment.transcript_version_id, segment.speaker_label)
         segment.id, segment.transcript_version_id, segment.speaker_label,
         segment.starts_at_seconds, segment.ends_at_seconds,
         transcript.organization_id, transcript.client_id, transcript.session_id
  FROM app.transcript_segments segment
  JOIN app.transcript_versions transcript ON transcript.id=segment.transcript_version_id
  WHERE segment.speaker_label IS NOT NULL
    AND length(trim(segment.speaker_label)) > 0
    AND segment.ends_at_seconds > segment.starts_at_seconds
  ORDER BY segment.transcript_version_id, segment.speaker_label,
           (segment.ends_at_seconds-segment.starts_at_seconds) DESC,
           segment.sequence_number
) chosen
JOIN LATERAL (
  SELECT artifact.id
  FROM app.clinical_artifacts artifact
  WHERE artifact.organization_id=chosen.organization_id
    AND artifact.client_id=chosen.client_id
    AND artifact.session_id=chosen.session_id
    AND artifact.artifact_type='audio_recording'
    AND artifact.lifecycle_state='active'
    AND artifact.deleted_at IS NULL
  ORDER BY artifact.created_at DESC
  LIMIT 1
) audio ON true;

COMMIT;
