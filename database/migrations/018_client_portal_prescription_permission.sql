BEGIN;

ALTER TABLE app.client_portal_permissions
  ADD COLUMN IF NOT EXISTS can_view_prescriptions boolean NOT NULL DEFAULT false;

COMMIT;
