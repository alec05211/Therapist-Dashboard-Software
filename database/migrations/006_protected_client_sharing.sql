BEGIN;

-- Explicitly bind the synthetic filesystem case; never infer it from login names.
ALTER TABLE app.client_portal_accounts
  ADD COLUMN IF NOT EXISTS synthetic_case_key text UNIQUE;

-- Existing synthetic setup only. Ambiguous names deliberately remain unbound.
UPDATE app.client_portal_accounts SET synthetic_case_key = 'heartwell-sadic'
WHERE display_name = 'Elena Sadić'
  AND (SELECT count(*) FROM app.client_portal_accounts WHERE display_name = 'Elena Sadić') = 1
  AND synthetic_case_key IS NULL;

-- New relationships fail closed. Preserve existing therapist choices.
ALTER TABLE app.client_portal_permissions
  ALTER COLUMN can_view_session_history SET DEFAULT false,
  ALTER COLUMN can_view_shared_transcripts SET DEFAULT false;

COMMIT;
