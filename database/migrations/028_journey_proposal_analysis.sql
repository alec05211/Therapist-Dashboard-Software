BEGIN;

ALTER TABLE app.client_journey_entries
  ADD COLUMN source_insight_snapshot_id uuid REFERENCES app.longitudinal_insight_snapshots(id) ON DELETE SET NULL,
  ADD COLUMN proposal_generator_name text,
  ADD COLUMN proposal_generator_version text,
  ADD COLUMN proposal_analysis jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX client_journey_entries_source_snapshot
  ON app.client_journey_entries (source_insight_snapshot_id)
  WHERE source_insight_snapshot_id IS NOT NULL;

COMMIT;
