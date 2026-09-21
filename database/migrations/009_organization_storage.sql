BEGIN;

CREATE TABLE app.organization_storage (
  organization_id uuid PRIMARY KEY REFERENCES app.organizations(id),
  bucket text NOT NULL UNIQUE,
  region text NOT NULL,
  kms_key_arn text NOT NULL,
  healthscribe_role_arn text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE app.session_storage_jobs (
  runtime_id text PRIMARY KEY,
  session_id uuid NOT NULL UNIQUE REFERENCES app.sessions(id),
  organization_id uuid NOT NULL REFERENCES app.organization_storage(organization_id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  job_name text NOT NULL UNIQUE,
  storage jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('UPLOADING', 'IN_PROGRESS', 'COMPLETED', 'FAILED')),
  detail text,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX session_storage_jobs_scope ON app.session_storage_jobs(organization_id, client_id, created_at DESC);

COMMIT;
