-- Durable, reviewable longitudinal-memory records.
--
-- These tables keep clinical-note revisions, longitudinal insight snapshots,
-- evidence lineage, and pre-session brief snapshots separate from a provider's
-- generated artifact. They do not authorize or automate clinical decisions.

BEGIN;

CREATE TABLE IF NOT EXISTS app.clinical_note_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  session_id uuid NOT NULL REFERENCES app.sessions(id),
  parent_version_id uuid REFERENCES app.clinical_note_versions(id),
  source_synthesis_version_id uuid REFERENCES app.synthesis_versions(id),
  version_number integer NOT NULL CHECK (version_number > 0),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'reviewed', 'finalized', 'superseded')),
  content jsonb NOT NULL,
  authored_by_user_id uuid REFERENCES app.application_users(id),
  finalized_by_user_id uuid REFERENCES app.application_users(id),
  finalized_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (session_id, version_number)
);

CREATE TABLE IF NOT EXISTS app.longitudinal_insight_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  parent_snapshot_id uuid REFERENCES app.longitudinal_insight_snapshots(id),
  source_cutoff_session_id uuid REFERENCES app.sessions(id),
  version_number integer NOT NULL CHECK (version_number > 0),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'reviewed', 'accepted', 'rejected', 'superseded')),
  generator_name text NOT NULL,
  generator_version text,
  selection_policy_version text NOT NULL,
  content jsonb NOT NULL,
  created_by_user_id uuid REFERENCES app.application_users(id),
  reviewed_by_user_id uuid REFERENCES app.application_users(id),
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (client_id, version_number)
);

CREATE TABLE IF NOT EXISTS app.longitudinal_insight_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  snapshot_id uuid NOT NULL REFERENCES app.longitudinal_insight_snapshots(id) ON DELETE CASCADE,
  item_kind text NOT NULL
    CHECK (item_kind IN ('trajectory', 'theme', 'open_thread', 'relevant_history', 'client_context', 'therapist_curated')),
  review_state text NOT NULL DEFAULT 'draft'
    CHECK (review_state IN ('draft', 'accepted', 'hidden', 'stale', 'disputed')),
  display_order integer NOT NULL DEFAULT 0,
  content jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app.longitudinal_insight_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  insight_item_id uuid NOT NULL REFERENCES app.longitudinal_insight_items(id) ON DELETE CASCADE,
  transcript_segment_id uuid REFERENCES app.transcript_segments(id),
  clinical_note_version_id uuid REFERENCES app.clinical_note_versions(id),
  evidence_role text NOT NULL DEFAULT 'supporting'
    CHECK (evidence_role IN ('supporting', 'contrasting', 'context')),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (transcript_segment_id IS NOT NULL OR clinical_note_version_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS app.pre_session_brief_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  upcoming_session_id uuid REFERENCES app.sessions(id),
  source_insight_snapshot_id uuid REFERENCES app.longitudinal_insight_snapshots(id),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'reviewed', 'accepted', 'discarded', 'superseded')),
  generator_name text NOT NULL,
  generator_version text,
  context_packet jsonb NOT NULL,
  content jsonb NOT NULL,
  created_by_user_id uuid REFERENCES app.application_users(id),
  reviewed_by_user_id uuid REFERENCES app.application_users(id),
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS clinical_note_versions_session_status_idx
  ON app.clinical_note_versions (session_id, status, version_number DESC);
CREATE INDEX IF NOT EXISTS longitudinal_insight_snapshots_client_status_idx
  ON app.longitudinal_insight_snapshots (organization_id, client_id, status, version_number DESC);
CREATE INDEX IF NOT EXISTS longitudinal_insight_items_snapshot_order_idx
  ON app.longitudinal_insight_items (snapshot_id, item_kind, display_order);
CREATE INDEX IF NOT EXISTS longitudinal_insight_evidence_segment_idx
  ON app.longitudinal_insight_evidence (transcript_segment_id);
CREATE INDEX IF NOT EXISTS pre_session_brief_snapshots_client_created_idx
  ON app.pre_session_brief_snapshots (organization_id, client_id, created_at DESC);

COMMIT;
