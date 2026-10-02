BEGIN;

CREATE TABLE app.client_speaker_label_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  source_label text NOT NULL,
  display_name text NOT NULL,
  updated_by_user_id uuid NOT NULL REFERENCES app.application_users(id),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (client_id, source_label),
  CHECK (length(trim(source_label)) > 0),
  CHECK (source_label = upper(source_label)),
  CHECK (length(trim(display_name)) > 0)
);

CREATE INDEX client_speaker_label_profiles_scope
  ON app.client_speaker_label_profiles (organization_id, client_id);

COMMIT;
