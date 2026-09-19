BEGIN;

ALTER TABLE app.client_portal_permissions
  ADD COLUMN IF NOT EXISTS can_view_session_history boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS can_view_insights boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS can_view_draft_notes boolean NOT NULL DEFAULT false;

ALTER TABLE app.client_portal_permissions
  ALTER COLUMN can_view_shared_transcripts SET DEFAULT true;

UPDATE app.client_portal_permissions
SET can_view_session_history = true,
    can_view_shared_transcripts = true
WHERE can_view_session_history = false OR can_view_shared_transcripts = false;

COMMIT;
