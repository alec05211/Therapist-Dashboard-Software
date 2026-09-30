BEGIN;

-- Session labels, dates, and future appointments are fixed client access.
-- Detailed transcript, recording, note, insight, and prescription material
-- remains controlled by its existing independent permission.
UPDATE app.client_portal_permissions
SET can_view_session_history = true
WHERE NOT can_view_session_history;

ALTER TABLE app.client_portal_permissions
  ALTER COLUMN can_view_session_history SET DEFAULT true;

COMMIT;
