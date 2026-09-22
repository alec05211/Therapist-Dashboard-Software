BEGIN;

ALTER TABLE app.account_profiles
  ADD COLUMN pronouns text CHECK (pronouns IS NULL OR char_length(pronouns) <= 80);

-- Pronouns are self-managed account information, not therapist-managed client
-- identification metadata. Keep the legacy column intact so this migration
-- never destroys previously stored values; the application no longer reads or
-- writes it.

COMMIT;
