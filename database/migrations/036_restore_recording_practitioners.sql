-- Recover the recording owner only when the appointment or creator identifies
-- exactly one practitioner in the session organization.
WITH candidates AS (
 SELECT s.id AS session_id, p.id AS practitioner_id,
        count(*) OVER (PARTITION BY s.id) AS candidate_count
 FROM app.sessions s
 LEFT JOIN app.appointments appointment ON appointment.id=s.appointment_id
 JOIN app.organization_memberships m ON m.organization_id=s.organization_id
 JOIN app.organization_practitioners p ON p.membership_id=m.id AND p.organization_id=s.organization_id
 WHERE ((appointment.primary_practitioner_id IS NOT NULL AND p.id=appointment.primary_practitioner_id)
    OR (appointment.primary_practitioner_id IS NULL AND m.user_id=s.created_by_user_id))
 AND NOT EXISTS (SELECT 1 FROM app.session_practitioner_participants participant WHERE participant.session_id=s.id)
)
INSERT INTO app.session_practitioner_participants(session_id, practitioner_id, participation_role)
SELECT session_id, practitioner_id, 'therapist' FROM candidates WHERE candidate_count=1
ON CONFLICT (session_id, practitioner_id) DO NOTHING;
