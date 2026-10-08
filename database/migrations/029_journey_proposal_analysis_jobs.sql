BEGIN;

CREATE TABLE app.journey_proposal_analysis_jobs (
  session_id uuid PRIMARY KEY REFERENCES app.sessions(id) ON DELETE CASCADE,
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  source_transcript_version_id uuid NOT NULL REFERENCES app.transcript_versions(id),
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'blocked')),
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  not_before timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  worker_token text,
  lease_expires_at timestamptz,
  input_fingerprint text,
  generator_name text,
  generator_version text,
  source_insight_snapshot_id uuid REFERENCES app.longitudinal_insight_snapshots(id) ON DELETE SET NULL,
  response_id text,
  usage jsonb NOT NULL DEFAULT '{}'::jsonb,
  last_error_code text,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at timestamptz,
  UNIQUE (organization_id, client_id, source_transcript_version_id)
);

CREATE INDEX journey_proposal_analysis_jobs_due_idx
  ON app.journey_proposal_analysis_jobs (not_before, created_at)
  WHERE status = 'pending';

COMMIT;
