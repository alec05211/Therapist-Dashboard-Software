-- Auth0 identities for clients are distinct from staff identities and never
-- inherit therapist access. Sharing decisions remain application-controlled.
BEGIN;

CREATE TABLE IF NOT EXISTS app.client_portal_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id uuid NOT NULL UNIQUE REFERENCES app.clients(id),
  auth0_subject text NOT NULL UNIQUE,
  display_name text NOT NULL,
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('invited', 'active', 'suspended', 'deactivated')),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deactivated_at timestamptz
);

CREATE INDEX IF NOT EXISTS client_portal_accounts_subject_idx
  ON app.client_portal_accounts (auth0_subject)
  WHERE status = 'active';

DROP TRIGGER IF EXISTS client_portal_accounts_set_updated_at ON app.client_portal_accounts;
CREATE TRIGGER client_portal_accounts_set_updated_at
BEFORE UPDATE ON app.client_portal_accounts
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

COMMIT;
