BEGIN;

ALTER TABLE app.clients
  ADD COLUMN display_name text,
  ADD COLUMN email text,
  ADD COLUMN phone text;

-- Practice contact details are deliberately separate from private login email.
ALTER TABLE app.organization_practitioners
  ADD COLUMN contact_email text,
  ADD COLUMN contact_phone text;

UPDATE app.clients client
SET display_name = portal.display_name,
    email = 'elena.sadic@example.com',
    phone = '(555) 014-2048'
FROM app.client_portal_accounts portal
WHERE portal.client_id = client.id AND portal.synthetic_case_key = 'heartwell-sadic';

UPDATE app.organization_practitioners practitioner
SET contact_email = 'jeremy.heartwell@example.com'
FROM app.client_therapist_access access, app.client_portal_accounts portal
WHERE access.practitioner_id = practitioner.id
  AND access.client_id = portal.client_id
  AND portal.synthetic_case_key = 'heartwell-sadic'
  AND practitioner.professional_name = 'Jeremy Heartwell'
  AND access.revoked_at IS NULL;

COMMIT;
