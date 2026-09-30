BEGIN;

-- A directory match is only a request to connect. Clinical access is created
-- after the client explicitly accepts the invitation.
CREATE TABLE app.client_connection_invitations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  registration_id uuid NOT NULL REFERENCES app.client_account_registrations(id),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  practitioner_id uuid NOT NULL REFERENCES app.organization_practitioners(id),
  invited_by_user_id uuid NOT NULL REFERENCES app.application_users(id),
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled')),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  responded_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX client_connection_invitations_one_pending
  ON app.client_connection_invitations (registration_id, practitioner_id)
  WHERE status = 'pending';

CREATE INDEX client_connection_invitations_registration_idx
  ON app.client_connection_invitations (registration_id, created_at DESC);

CREATE TRIGGER client_connection_invitations_set_updated_at
BEFORE UPDATE ON app.client_connection_invitations
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

COMMIT;
