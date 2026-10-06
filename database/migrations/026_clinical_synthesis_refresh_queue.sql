BEGIN;

CREATE TABLE app.clinical_synthesis_refresh_state (
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  desired_insights_revision bigint NOT NULL DEFAULT 0 CHECK (desired_insights_revision >= 0),
  published_insights_revision bigint NOT NULL DEFAULT 0 CHECK (published_insights_revision >= 0),
  processing_insights_revision bigint CHECK (processing_insights_revision >= 0),
  published_insight_snapshot_id uuid REFERENCES app.longitudinal_insight_snapshots(id),
  status text NOT NULL DEFAULT 'idle'
    CHECK (status IN ('idle', 'pending', 'running', 'failed')),
  pending_event_count integer NOT NULL DEFAULT 0 CHECK (pending_event_count >= 0),
  pending_since timestamptz,
  not_before timestamptz,
  worker_token text,
  lease_expires_at timestamptz,
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  last_event_at timestamptz,
  last_attempt_at timestamptz,
  last_published_at timestamptz,
  last_error_code text,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (organization_id, client_id),
  CHECK (published_insights_revision <= desired_insights_revision)
);

CREATE TABLE app.clinical_synthesis_refresh_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  desired_insights_revision bigint NOT NULL CHECK (desired_insights_revision > 0),
  event_type text NOT NULL,
  actor_user_id uuid REFERENCES app.application_users(id),
  target_type text,
  target_id uuid,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  consumed_at timestamptz,
  CHECK (length(trim(event_type)) > 0),
  CHECK (target_type IS NULL OR length(trim(target_type)) > 0)
);

CREATE INDEX clinical_synthesis_refresh_due_idx
  ON app.clinical_synthesis_refresh_state (not_before, pending_since)
  WHERE status = 'pending';

CREATE INDEX clinical_synthesis_refresh_events_client_idx
  ON app.clinical_synthesis_refresh_events
    (organization_id, client_id, desired_insights_revision, created_at);

CREATE INDEX clinical_synthesis_refresh_events_unconsumed_idx
  ON app.clinical_synthesis_refresh_events (created_at)
  WHERE consumed_at IS NULL;

CREATE TABLE app.pre_session_brief_refresh_state (
  appointment_id uuid PRIMARY KEY REFERENCES app.appointments(id) ON DELETE CASCADE,
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  source_insight_snapshot_id uuid NOT NULL REFERENCES app.longitudinal_insight_snapshots(id),
  desired_insights_revision bigint NOT NULL CHECK (desired_insights_revision > 0),
  published_insights_revision bigint NOT NULL DEFAULT 0 CHECK (published_insights_revision >= 0),
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'running', 'idle', 'failed')),
  not_before timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  worker_token text,
  lease_expires_at timestamptz,
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  last_error_code text,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (published_insights_revision <= desired_insights_revision)
);

CREATE INDEX pre_session_brief_refresh_due_idx
  ON app.pre_session_brief_refresh_state (not_before, appointment_id)
  WHERE status = 'pending';

WITH latest_accepted AS (
  SELECT DISTINCT ON (organization_id, client_id)
         organization_id, client_id, id, version_number, created_at
  FROM app.longitudinal_insight_snapshots
  WHERE status = 'accepted'
  ORDER BY organization_id, client_id, version_number DESC
)
INSERT INTO app.clinical_synthesis_refresh_state (
  organization_id, client_id, desired_insights_revision,
  published_insights_revision, published_insight_snapshot_id, status,
  last_published_at
)
SELECT organization_id, client_id, version_number, version_number, id, 'idle', created_at
FROM latest_accepted
ON CONFLICT (organization_id, client_id) DO NOTHING;

COMMIT;
