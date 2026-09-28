BEGIN;

ALTER TABLE app.appointments
  ADD COLUMN appointment_type text NOT NULL DEFAULT 'one_time'
    CHECK (appointment_type IN ('recurring', 'make_up', 'one_time')),
  ADD COLUMN series_id uuid,
  ADD COLUMN meeting_mode text NOT NULL DEFAULT 'in_person'
    CHECK (meeting_mode IN ('in_person', 'video', 'phone')),
  ADD COLUMN cancelled_at timestamptz,
  ADD COLUMN cancelled_by_user_id uuid REFERENCES app.application_users(id);

CREATE INDEX appointments_practitioner_time_idx
  ON app.appointments(primary_practitioner_id, starts_at)
  WHERE status IN ('scheduled', 'confirmed');
CREATE INDEX appointments_series_idx ON app.appointments(series_id) WHERE series_id IS NOT NULL;

CREATE TABLE app.client_scheduling_preferences (
  client_id uuid PRIMARY KEY REFERENCES app.clients(id) ON DELETE CASCADE,
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  practitioner_id uuid NOT NULL REFERENCES app.organization_practitioners(id),
  cadence_weeks smallint NOT NULL DEFAULT 1 CHECK (cadence_weeks IN (1, 2, 4)),
  duration_minutes smallint NOT NULL DEFAULT 50 CHECK (duration_minutes BETWEEN 20 AND 180),
  meeting_mode text NOT NULL DEFAULT 'in_person' CHECK (meeting_mode IN ('in_person', 'video', 'phone')),
  timezone text NOT NULL DEFAULT 'America/New_York',
  preferred_weekday smallint CHECK (preferred_weekday BETWEEN 0 AND 6),
  preferred_start_local time,
  updated_by_user_id uuid REFERENCES app.application_users(id),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (organization_id, client_id, practitioner_id)
);

-- Existing primary clinicians who can edit the clinical record can manage the
-- corresponding schedule. Future grants remain explicit at creation time.
UPDATE app.client_therapist_access
SET can_manage_sessions=true, updated_at=CURRENT_TIMESTAMP
WHERE relationship_type='primary' AND revoked_at IS NULL
  AND can_write_clinical AND NOT can_manage_sessions;

INSERT INTO app.client_scheduling_preferences
  (organization_id, client_id, practitioner_id, cadence_weeks, duration_minutes,
   meeting_mode, timezone, preferred_weekday, preferred_start_local)
SELECT client.organization_id, client.id, access.practitioner_id, 1, 50,
       'in_person', 'America/New_York', 0, TIME '15:00'
FROM app.client_portal_accounts portal
JOIN app.clients client ON client.id=portal.client_id
JOIN app.client_therapist_access access ON access.client_id=client.id
  AND access.organization_id=client.organization_id
WHERE portal.synthetic_case_key='heartwell-sadic' AND portal.status='active'
  AND access.relationship_type='primary' AND access.revoked_at IS NULL
ON CONFLICT (client_id) DO NOTHING;

INSERT INTO app.appointments
  (organization_id, client_id, primary_practitioner_id, starts_at, ends_at,
   status, appointment_type, series_id, meeting_mode)
SELECT preference.organization_id, preference.client_id, preference.practitioner_id,
       slot.starts_at, slot.starts_at + interval '50 minutes', 'scheduled',
       'recurring', 'f0a1386c-676b-4d03-9e79-20bc249af807'::uuid, preference.meeting_mode
FROM app.client_scheduling_preferences preference
CROSS JOIN (VALUES
  ('2026-09-28 15:00:00-04'::timestamptz), ('2026-10-05 15:00:00-04'::timestamptz),
  ('2026-10-12 15:00:00-04'::timestamptz), ('2026-10-19 15:00:00-04'::timestamptz),
  ('2026-10-26 15:00:00-04'::timestamptz), ('2026-11-02 15:00:00-05'::timestamptz),
  ('2026-11-09 15:00:00-05'::timestamptz)
) AS slot(starts_at)
JOIN app.client_portal_accounts portal ON portal.client_id=preference.client_id
  AND portal.synthetic_case_key='heartwell-sadic'
WHERE NOT EXISTS (
  SELECT 1 FROM app.appointments existing
  WHERE existing.client_id=preference.client_id
    AND existing.primary_practitioner_id=preference.practitioner_id
    AND existing.starts_at=slot.starts_at
);

COMMIT;
