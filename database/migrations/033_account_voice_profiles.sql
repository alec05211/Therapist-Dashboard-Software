BEGIN;
CREATE TABLE app.account_voice_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject text NOT NULL UNIQUE,
    embedding jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE app.transcript_voice_assignments (
    transcript_version_id uuid REFERENCES app.transcript_versions(id) ON DELETE CASCADE,
    source_label text NOT NULL,
    participant_role text NOT NULL CHECK (participant_role IN ('therapist', 'client')),
    profile_id uuid NOT NULL REFERENCES app.account_voice_profiles(id) ON DELETE CASCADE,
    PRIMARY KEY (transcript_version_id, source_label)
);
COMMIT;
