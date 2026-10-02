BEGIN;

ALTER TABLE app.session_storage_jobs
  DROP CONSTRAINT IF EXISTS session_storage_jobs_status_check;

ALTER TABLE app.session_storage_jobs
  ADD CONSTRAINT session_storage_jobs_status_check CHECK (status IN (
    'UPLOADING',
    'QUEUED',
    'IN_PROGRESS',
    'RETRIEVING_RESULTS',
    'PREPARING_TRANSCRIPT',
    'SAVING_SESSION',
    'COMPLETED',
    'FAILED'
  ));

CREATE INDEX IF NOT EXISTS session_storage_jobs_active
  ON app.session_storage_jobs (organization_id, client_id, updated_at DESC)
  WHERE status NOT IN ('COMPLETED', 'FAILED');

COMMIT;
