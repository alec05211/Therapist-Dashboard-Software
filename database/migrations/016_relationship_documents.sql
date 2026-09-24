BEGIN;

ALTER TABLE app.client_documents
  ADD COLUMN practitioner_id uuid REFERENCES app.organization_practitioners(id),
  ADD COLUMN signed_artifact_id uuid UNIQUE REFERENCES app.clinical_artifacts(id),
  ADD COLUMN signer_portal_account_id uuid REFERENCES app.client_portal_accounts(id),
  ADD COLUMN signer_name text,
  ADD COLUMN signature_consent text,
  ADD COLUMN original_sha256 text,
  ADD COLUMN pdf_page_count integer CHECK (pdf_page_count BETWEEN 1 AND 100);

-- Bind legacy documents only when their uploader identifies one practitioner.
UPDATE app.client_documents document SET practitioner_id = practitioner.id
FROM app.organization_practitioners practitioner
JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id
WHERE membership.user_id=document.uploaded_by_user_id
  AND membership.organization_id=document.organization_id;

-- Unresolved legacy rows stay inaccessible until explicitly assigned.
ALTER TABLE app.client_documents DROP CONSTRAINT client_documents_client_id_title_version_number_key;
CREATE INDEX client_documents_relationship ON app.client_documents
  (organization_id, client_id, practitioner_id, created_at DESC);

COMMIT;
