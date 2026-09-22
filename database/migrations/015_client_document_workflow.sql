BEGIN;

ALTER TABLE app.client_documents
  ADD COLUMN workflow_status text NOT NULL DEFAULT 'draft'
    CHECK (workflow_status IN ('draft', 'pending_signature', 'completed', 'signed')),
  ADD COLUMN completed_at timestamptz,
  ADD COLUMN signed_at timestamptz;

CREATE TABLE app.client_document_pages (
  document_id uuid NOT NULL REFERENCES app.client_documents(id) ON DELETE CASCADE,
  page_number integer NOT NULL CHECK (page_number > 0),
  artifact_id uuid NOT NULL UNIQUE REFERENCES app.clinical_artifacts(id),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (document_id, page_number)
);

COMMIT;
