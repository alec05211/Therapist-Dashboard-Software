BEGIN;

CREATE TABLE app.client_journey_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  session_id uuid NOT NULL REFERENCES app.sessions(id),
  source_summary_key text NOT NULL,
  source_provider text NOT NULL,
  category text NOT NULL DEFAULT 'context'
    CHECK (category IN ('context', 'theme', 'important_quote', 'resolution', 'breakthrough', 'open_thread')),
  content text NOT NULL CHECK (length(trim(content)) > 0),
  status text NOT NULL DEFAULT 'proposed'
    CHECK (status IN ('proposed', 'accepted', 'rejected', 'hidden', 'stale', 'disputed')),
  reviewed_by_user_id uuid REFERENCES app.application_users(id),
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (session_id, source_summary_key)
);

CREATE TABLE app.client_journey_evidence (
  journey_entry_id uuid NOT NULL REFERENCES app.client_journey_entries(id) ON DELETE CASCADE,
  transcript_segment_id uuid NOT NULL REFERENCES app.transcript_segments(id),
  PRIMARY KEY (journey_entry_id, transcript_segment_id)
);

CREATE TABLE app.client_journey_entry_revisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  journey_entry_id uuid NOT NULL REFERENCES app.client_journey_entries(id),
  previous_status text NOT NULL,
  next_status text NOT NULL,
  previous_category text NOT NULL,
  next_category text NOT NULL,
  previous_content text NOT NULL,
  next_content text NOT NULL,
  changed_by_user_id uuid NOT NULL REFERENCES app.application_users(id),
  changed_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX client_journey_entries_scope
  ON app.client_journey_entries (organization_id, client_id, status, created_at DESC);

COMMIT;
