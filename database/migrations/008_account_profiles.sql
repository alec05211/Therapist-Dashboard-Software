BEGIN;

-- Photos and optional public biography belong to the account. Login email stays
-- separate from the contact address the account chooses to share.
CREATE TABLE app.account_profiles (
  auth0_subject text PRIMARY KEY,
  photo bytea,
  photo_mime text CHECK (photo_mime IN ('image/jpeg', 'image/png', 'image/webp')),
  about_me text CHECK (char_length(about_me) <= 2000),
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK ((photo IS NULL) = (photo_mime IS NULL)),
  CHECK (photo IS NULL OR octet_length(photo) <= 2 * 1024 * 1024)
);

CREATE TRIGGER account_profiles_set_updated_at
BEFORE UPDATE ON app.account_profiles
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

COMMIT;
