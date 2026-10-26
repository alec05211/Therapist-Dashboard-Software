BEGIN;

CREATE TABLE app.client_diagnostic_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id) ON DELETE CASCADE,
  event_type text NOT NULL,
  level text NOT NULL CHECK (level IN ('info', 'warning', 'error')),
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX client_diagnostic_events_timeline_idx
  ON app.client_diagnostic_events (organization_id, client_id, created_at DESC, id);

COMMIT;
