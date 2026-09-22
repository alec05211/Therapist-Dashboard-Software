BEGIN;

CREATE TABLE app.client_identification_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  participant_role text NOT NULL CHECK (participant_role IN ('client', 'therapist')),
  display_name text NOT NULL CHECK (length(trim(display_name)) > 0),
  pronouns text,
  updated_by_user_id uuid NOT NULL REFERENCES app.application_users(id),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (client_id, participant_role)
);

CREATE INDEX client_identification_profiles_scope
  ON app.client_identification_profiles (organization_id, client_id);

COMMIT;
