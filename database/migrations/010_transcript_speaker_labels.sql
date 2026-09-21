BEGIN;

CREATE TABLE app.transcript_speaker_labels (
  transcript_version_id uuid NOT NULL REFERENCES app.transcript_versions(id) ON DELETE CASCADE,
  source_label text NOT NULL,
  display_label text NOT NULL,
  updated_by_user_id uuid REFERENCES app.application_users(id),
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (transcript_version_id, source_label),
  CHECK (length(trim(source_label)) > 0),
  CHECK (length(trim(display_label)) > 0)
);

COMMIT;
