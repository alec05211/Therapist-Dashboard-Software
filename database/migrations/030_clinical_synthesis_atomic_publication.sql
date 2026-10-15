BEGIN;

ALTER TABLE app.pre_session_brief_snapshots
  ADD COLUMN appointment_id uuid REFERENCES app.appointments(id) ON DELETE CASCADE;

CREATE INDEX pre_session_brief_snapshots_appointment_created_idx
  ON app.pre_session_brief_snapshots (appointment_id, created_at DESC)
  WHERE appointment_id IS NOT NULL;

ALTER TABLE app.pre_session_brief_refresh_state
  ADD COLUMN published_brief_snapshot_id uuid REFERENCES app.pre_session_brief_snapshots(id),
  ADD COLUMN last_published_at timestamptz;

COMMIT;
