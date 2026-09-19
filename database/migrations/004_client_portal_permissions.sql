-- Client-facing material is denied unless a therapist explicitly enables a
-- category. This does not replace consent or session-level sharing review.
BEGIN;

CREATE TABLE IF NOT EXISTS app.client_portal_permissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL UNIQUE REFERENCES app.clients(id),
  can_view_approved_summaries boolean NOT NULL DEFAULT false,
  can_view_shared_transcripts boolean NOT NULL DEFAULT false,
  can_play_shared_recordings boolean NOT NULL DEFAULT false,
  updated_by_user_id uuid REFERENCES app.application_users(id),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DROP TRIGGER IF EXISTS client_portal_permissions_set_updated_at ON app.client_portal_permissions;
CREATE TRIGGER client_portal_permissions_set_updated_at
BEFORE UPDATE ON app.client_portal_permissions
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

COMMIT;
