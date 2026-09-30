BEGIN;

-- An Auth0 identity can register as a discoverable client before it belongs to
-- a practice. Connecting it creates the organization-scoped client and portal
-- records; registration alone grants no clinical access.
CREATE TABLE app.client_account_registrations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  auth0_subject text NOT NULL UNIQUE,
  first_name text NOT NULL CHECK (length(trim(first_name)) > 0),
  last_name text NOT NULL CHECK (length(trim(last_name)) > 0),
  email text,
  discoverable boolean NOT NULL DEFAULT true,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'connected', 'deactivated')),
  connected_client_id uuid UNIQUE REFERENCES app.clients(id),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK ((status = 'connected') = (connected_client_id IS NOT NULL))
);

CREATE INDEX client_account_registrations_directory_idx
  ON app.client_account_registrations (last_name, first_name)
  WHERE discoverable AND status = 'pending';

CREATE TRIGGER client_account_registrations_set_updated_at
BEFORE UPDATE ON app.client_account_registrations
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

COMMIT;
