# Synthetic client sharing

Profile headers load `/relationship-profile` through the authenticated API.
Client display name, email, and phone live in `app.clients`; therapist public
practice email and phone live in `app.organization_practitioners` alongside
their professional name. Login emails are not used as public contact details.
Missing contact fields are omitted. The endpoint resolves the caller's active
relationship, and refuses missing or ambiguous therapist profiles.
Migration `007_relationship_contact_profiles.sql` seeds only the existing
synthetic case's former presentation values; it leaves therapist phone blank.

Jeremy's Client care settings → Permissions controls persist in
`app.client_portal_permissions`. The API resolves his active membership,
practitioner record, and client-specific access grant before reading or saving.
Writes require clinical write access and reject mismatched client/organization
IDs. Missing permission rows deny every category.

Migration `006_protected_client_sharing.sql` binds the existing, uniquely named
Elena synthetic account to `heartwell-sadic`. Runtime authorization uses this
explicit database binding and verified Auth0 subjects, never display names.
The migration preserves existing permission choices and makes new rows deny
history/transcript access by default.

Elena's `/client-portal` response contains only enabled categories. History
contains labels/dates without transcript excerpts. Transcripts and draft notes
are independently shared from the six explicitly mapped synthetic sessions;
runtime recordings and provider metadata are excluded. Recording playback is a
separate permission, requiring transcript sharing too. The client recording
endpoint rechecks identity and both permissions before serving any audio,
including byte-range requests. Insights contain only
accepted item text from the latest accepted-state snapshot; evidence and hidden,
stale, disputed, or draft items are excluded. An enabled insights section remains
empty when no approved items exist. This flow does not approve generated insights.

The portal refreshes on window focus and every minute, clearing prior materials
on failure or revocation while preserving playback during successful refreshes. The server rechecks permissions on every request and uses
`Cache-Control: no-store`. Already displayed information cannot be recalled.
Legacy transcript, recording, demo insight, and recording-upload routes require
linked therapist access, including direct backend requests. The authenticated
Next.js API handler forwards the access token for these requests.

Validation:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m tests.verify_client_sharing_database
```

The second command requires the configured synthetic database/AWS connection.
It checks actual save/reload, portal filtering, role separation, and revoked
access with token validation replaced by known database identities. All test
writes roll back. It does not validate the external Auth0 login flow.
