BEGIN;

CREATE TABLE app.client_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  title text NOT NULL CHECK (length(trim(title)) > 0),
  document_type text NOT NULL
    CHECK (document_type IN ('consent_form', 'report', 'assessment', 'correspondence', 'other')),
  source_filename text NOT NULL CHECK (length(trim(source_filename)) > 0),
  content_artifact_id uuid NOT NULL UNIQUE REFERENCES app.clinical_artifacts(id),
  thumbnail_artifact_id uuid UNIQUE REFERENCES app.clinical_artifacts(id),
  version_number integer NOT NULL DEFAULT 1 CHECK (version_number > 0),
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'archived', 'superseded', 'pending_deletion', 'deleted')),
  uploaded_by_user_id uuid NOT NULL REFERENCES app.application_users(id),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at timestamptz,
  UNIQUE (client_id, title, version_number)
);

CREATE INDEX client_documents_scope
  ON app.client_documents (organization_id, client_id, status, created_at DESC);

CREATE TRIGGER client_documents_set_updated_at
BEFORE UPDATE ON app.client_documents
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

COMMIT;
