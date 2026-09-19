# Account profiles and role-based UI

`AccountSettingsPage` is shared by therapist and client accounts. The Profile
form edits the signed-in account's display or professional name, contact email,
optional phone, and photo. Therapists also get About me. The Appearance module
is shared; therapist-only session navigation remains visible only to therapists.

`frontend/src/lib/role-capabilities.ts` is the UI feature map. Add a role to a
feature there to render its module. The server enforces the same sensitive
boundary independently: client accounts cannot write About me. A future client
description feature needs an explicit server policy change as well as the UI
capability change.

Contact data remains on `app.clients` and `app.organization_practitioners`.
`app.account_profiles` stores the account photo and optional biography under
the verified Auth0 subject. The profile API resolves only the signed-in active
account. Photos are limited to JPEG, PNG, or WebP under 2 MB and served through
authenticated, uncached endpoints. A relationship header fetches the other
person's photo and therapist biography only through its active care link.
Login email stays separate from the public contact email.

Migration `008_account_profiles.sql` adds the photo and biography table.
