-- Initial PostgreSQL schema for the therapist dashboard.
--
-- This is a deliberately adaptable starting point, not a final clinical-data
-- model. Apply future changes through reviewed migrations; do not edit a
-- production database by hand. This schema contains no RLS policies yet:
-- application authorization is mandatory until dedicated database roles and
-- tenant policies are introduced.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS app;

CREATE OR REPLACE FUNCTION app.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS app.organizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'suspended', 'archived')),
  settings jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  archived_at timestamptz
);

CREATE TABLE IF NOT EXISTS app.application_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  auth0_subject text NOT NULL UNIQUE,
  email text,
  display_name text,
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('invited', 'active', 'suspended', 'deactivated')),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deactivated_at timestamptz
);

CREATE TABLE IF NOT EXISTS app.organization_memberships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  user_id uuid NOT NULL REFERENCES app.application_users(id),
  auth0_organization_id text,
  role text NOT NULL
    CHECK (role IN ('owner', 'administrator', 'therapist', 'scheduler', 'billing')),
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('invited', 'active', 'suspended', 'ended')),
  starts_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ends_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (organization_id, user_id),
  CHECK (ends_at IS NULL OR ends_at > starts_at)
);

-- A practitioner is a therapist-capable membership. Keeping it distinct from
-- the identity allows one person to be a practitioner in more than one practice.
CREATE TABLE IF NOT EXISTS app.organization_practitioners (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  membership_id uuid NOT NULL UNIQUE REFERENCES app.organization_memberships(id),
  professional_name text,
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'inactive', 'suspended')),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app.clients (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('prospective', 'active', 'inactive', 'archived')),
  -- Demographic/contact fields will be added only after their access,
  -- encryption, retention, and client-facing policies are decided.
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  archived_at timestamptz
);

-- The central relationship table. Organization membership alone never grants
-- clinical access; every therapist-client association must be present here.
CREATE TABLE IF NOT EXISTS app.client_therapist_access (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  practitioner_id uuid NOT NULL REFERENCES app.organization_practitioners(id),
  relationship_type text NOT NULL
    CHECK (relationship_type IN ('primary', 'collaborating', 'supervising', 'temporary_coverage')),
  can_read_clinical boolean NOT NULL DEFAULT true,
  can_write_clinical boolean NOT NULL DEFAULT false,
  can_view_artifacts boolean NOT NULL DEFAULT false,
  can_manage_sessions boolean NOT NULL DEFAULT false,
  can_export boolean NOT NULL DEFAULT false,
  can_manage_client_access boolean NOT NULL DEFAULT false,
  effective_from timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  effective_until timestamptz,
  granted_by_user_id uuid REFERENCES app.application_users(id),
  grant_reason text,
  revoked_at timestamptz,
  revoked_by_user_id uuid REFERENCES app.application_users(id),
  revocation_reason text,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (effective_until IS NULL OR effective_until > effective_from),
  CHECK (revoked_at IS NULL OR revoked_at >= effective_from),
  CHECK (can_read_clinical OR NOT (can_write_clinical OR can_view_artifacts OR can_manage_sessions OR can_export OR can_manage_client_access))
);

-- Only one non-revoked grant of a particular relationship type may be recorded
-- for a therapist/client pair. A later policy migration will add temporal
-- conflict prevention for overlapping primary or temporary-coverage periods.
CREATE UNIQUE INDEX IF NOT EXISTS client_therapist_access_active_relationship
  ON app.client_therapist_access (client_id, practitioner_id, relationship_type)
  WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS app.appointments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  primary_practitioner_id uuid REFERENCES app.organization_practitioners(id),
  starts_at timestamptz NOT NULL,
  ends_at timestamptz NOT NULL,
  status text NOT NULL DEFAULT 'scheduled'
    CHECK (status IN ('scheduled', 'confirmed', 'cancelled', 'completed', 'no_show')),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (ends_at > starts_at)
);

CREATE TABLE IF NOT EXISTS app.sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  appointment_id uuid REFERENCES app.appointments(id),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'recording', 'processing', 'review', 'finalized', 'cancelled')),
  started_at timestamptz,
  ended_at timestamptz,
  created_by_user_id uuid REFERENCES app.application_users(id),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at)
);

-- Captures who participated in a particular session without changing the
-- current client access grant or historical session attribution.
CREATE TABLE IF NOT EXISTS app.session_practitioner_participants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES app.sessions(id),
  practitioner_id uuid NOT NULL REFERENCES app.organization_practitioners(id),
  client_therapist_access_id uuid REFERENCES app.client_therapist_access(id),
  participation_role text NOT NULL DEFAULT 'therapist'
    CHECK (participation_role IN ('therapist', 'supervisor', 'covering_therapist', 'observer')),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (session_id, practitioner_id)
);

CREATE TABLE IF NOT EXISTS app.clinical_artifacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  session_id uuid REFERENCES app.sessions(id),
  artifact_type text NOT NULL
    CHECK (artifact_type IN ('audio_recording', 'raw_transcript', 'raw_clinical_document', 'normalized_transcript_export', 'synthesis_export', 'attachment')),
  source text NOT NULL DEFAULT 'application'
    CHECK (source IN ('application', 'healthscribe', 'future_processor', 'user_upload')),
  storage_bucket text NOT NULL,
  object_key text NOT NULL,
  object_version_id text,
  content_type text NOT NULL,
  byte_size bigint CHECK (byte_size IS NULL OR byte_size >= 0),
  sha256_checksum text,
  encryption_key_reference text,
  lifecycle_state text NOT NULL DEFAULT 'active'
    CHECK (lifecycle_state IN ('processing', 'active', 'archived', 'pending_deletion', 'deleted')),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at timestamptz,
  UNIQUE (storage_bucket, object_key, object_version_id)
);

CREATE TABLE IF NOT EXISTS app.transcript_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  session_id uuid NOT NULL REFERENCES app.sessions(id),
  source_artifact_id uuid REFERENCES app.clinical_artifacts(id),
  parent_version_id uuid REFERENCES app.transcript_versions(id),
  version_number integer NOT NULL CHECK (version_number > 0),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'reviewed', 'finalized', 'superseded')),
  source_provider text,
  source_provider_version text,
  created_by_user_id uuid REFERENCES app.application_users(id),
  finalized_by_user_id uuid REFERENCES app.application_users(id),
  finalized_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (session_id, version_number)
);

CREATE TABLE IF NOT EXISTS app.transcript_segments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  transcript_version_id uuid NOT NULL REFERENCES app.transcript_versions(id),
  sequence_number integer NOT NULL CHECK (sequence_number >= 0),
  starts_at_seconds numeric(12, 3) NOT NULL CHECK (starts_at_seconds >= 0),
  ends_at_seconds numeric(12, 3) NOT NULL CHECK (ends_at_seconds >= starts_at_seconds),
  speaker_label text,
  content text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (transcript_version_id, sequence_number)
);

CREATE TABLE IF NOT EXISTS app.synthesis_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  session_id uuid NOT NULL REFERENCES app.sessions(id),
  source_transcript_version_id uuid NOT NULL REFERENCES app.transcript_versions(id),
  parent_version_id uuid REFERENCES app.synthesis_versions(id),
  version_number integer NOT NULL CHECK (version_number > 0),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'reviewed', 'accepted', 'rejected', 'superseded')),
  generator_name text NOT NULL,
  generator_version text,
  content jsonb NOT NULL,
  created_by_user_id uuid REFERENCES app.application_users(id),
  reviewed_by_user_id uuid REFERENCES app.application_users(id),
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (session_id, version_number)
);

CREATE TABLE IF NOT EXISTS app.consent_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  session_id uuid REFERENCES app.sessions(id),
  consent_type text NOT NULL
    CHECK (consent_type IN ('recording', 'transcription', 'ai_synthesis', 'client_sharing', 'model_evaluation_or_training')),
  status text NOT NULL CHECK (status IN ('granted', 'withdrawn', 'expired', 'declined')),
  policy_version text NOT NULL,
  granted_at timestamptz,
  withdrawn_at timestamptz,
  recorded_by_user_id uuid REFERENCES app.application_users(id),
  evidence_artifact_id uuid REFERENCES app.clinical_artifacts(id),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK ((status = 'granted' AND granted_at IS NOT NULL) OR status <> 'granted')
);

CREATE TABLE IF NOT EXISTS app.audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid REFERENCES app.organizations(id),
  actor_user_id uuid REFERENCES app.application_users(id),
  action text NOT NULL,
  target_type text NOT NULL,
  target_id uuid,
  outcome text NOT NULL CHECK (outcome IN ('allowed', 'denied', 'failed')),
  occurred_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  request_id text,
  ip_address inet,
  user_agent text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS organization_memberships_user_idx
  ON app.organization_memberships (user_id, organization_id);
CREATE INDEX IF NOT EXISTS clients_organization_idx
  ON app.clients (organization_id, status);
CREATE INDEX IF NOT EXISTS client_therapist_access_authorization_idx
  ON app.client_therapist_access (organization_id, client_id, practitioner_id)
  WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS appointments_client_time_idx
  ON app.appointments (organization_id, client_id, starts_at DESC);
CREATE INDEX IF NOT EXISTS sessions_client_time_idx
  ON app.sessions (organization_id, client_id, started_at DESC);
CREATE INDEX IF NOT EXISTS clinical_artifacts_session_idx
  ON app.clinical_artifacts (organization_id, session_id, lifecycle_state);
CREATE INDEX IF NOT EXISTS audit_events_target_idx
  ON app.audit_events (organization_id, target_type, target_id, occurred_at DESC);

DROP TRIGGER IF EXISTS organizations_set_updated_at ON app.organizations;
CREATE TRIGGER organizations_set_updated_at
BEFORE UPDATE ON app.organizations
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS application_users_set_updated_at ON app.application_users;
CREATE TRIGGER application_users_set_updated_at
BEFORE UPDATE ON app.application_users
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS organization_memberships_set_updated_at ON app.organization_memberships;
CREATE TRIGGER organization_memberships_set_updated_at
BEFORE UPDATE ON app.organization_memberships
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS organization_practitioners_set_updated_at ON app.organization_practitioners;
CREATE TRIGGER organization_practitioners_set_updated_at
BEFORE UPDATE ON app.organization_practitioners
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS clients_set_updated_at ON app.clients;
CREATE TRIGGER clients_set_updated_at
BEFORE UPDATE ON app.clients
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS client_therapist_access_set_updated_at ON app.client_therapist_access;
CREATE TRIGGER client_therapist_access_set_updated_at
BEFORE UPDATE ON app.client_therapist_access
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS appointments_set_updated_at ON app.appointments;
CREATE TRIGGER appointments_set_updated_at
BEFORE UPDATE ON app.appointments
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

DROP TRIGGER IF EXISTS sessions_set_updated_at ON app.sessions;
CREATE TRIGGER sessions_set_updated_at
BEFORE UPDATE ON app.sessions
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

COMMIT;
