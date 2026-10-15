"""Durable, client-scoped control plane for clinical synthesis refresh work.

Request handlers only append events and revision intent. Model calls belong in a
separate worker that leases due revisions through this module.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from psycopg.types.json import Json


EVENT_TYPES = {
    "clinical_note_finalized",
    "clinical_note_amended",
    "transcript_finalized",
    "transcript_corrected",
    "evidence_claim_accepted",
    "evidence_claim_dismissed",
    "evidence_claim_edited",
    "insight_hidden",
    "insight_disputed",
    "insight_pinned",
    "insight_outdated",
    "clinician_context_changed",
    "reprocess_requested",
}

PROMPT_EVENT_TYPES = {
    "clinical_note_finalized",
    "clinical_note_amended",
    "transcript_finalized",
    "transcript_corrected",
    "evidence_claim_accepted",
    "evidence_claim_dismissed",
}


def enqueue_next_appointment_brief(
    connection: Any,
    *,
    organization_id: str,
    client_id: str,
) -> bool:
    """Queue the next appointment when a validated Insights snapshot exists."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO app.pre_session_brief_refresh_state AS brief_state (
              appointment_id, organization_id, client_id, source_insight_snapshot_id,
              desired_insights_revision, status, not_before
            )
            SELECT appointment.id, appointment.organization_id, appointment.client_id,
                   state.published_insight_snapshot_id, state.published_insights_revision,
                   'pending', CURRENT_TIMESTAMP
            FROM app.appointments AS appointment
            JOIN app.clinical_synthesis_refresh_state AS state
              ON state.organization_id = appointment.organization_id
             AND state.client_id = appointment.client_id
            WHERE appointment.organization_id = %s AND appointment.client_id = %s
              AND appointment.status IN ('scheduled', 'confirmed')
              AND appointment.ends_at > CURRENT_TIMESTAMP
              AND state.published_insight_snapshot_id IS NOT NULL
              AND state.published_insights_revision > 0
            ORDER BY appointment.starts_at
            LIMIT 1
            ON CONFLICT (appointment_id) DO UPDATE SET
              source_insight_snapshot_id = EXCLUDED.source_insight_snapshot_id,
              desired_insights_revision = EXCLUDED.desired_insights_revision,
              status = CASE
                WHEN brief_state.published_insights_revision >= EXCLUDED.desired_insights_revision
                  THEN brief_state.status
                WHEN brief_state.status = 'running' THEN 'running'
                ELSE 'pending'
              END,
              not_before = CASE
                WHEN brief_state.published_insights_revision >= EXCLUDED.desired_insights_revision
                  THEN brief_state.not_before
                ELSE CURRENT_TIMESTAMP
              END,
              updated_at = CURRENT_TIMESTAMP
            RETURNING appointment_id
            """,
            (organization_id, client_id),
        )
        return cursor.fetchone() is not None


def enqueue_insights_refresh(
    connection: Any,
    *,
    organization_id: str,
    client_id: str,
    event_type: str,
    actor_user_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    debounce_seconds: int = 120,
    maximum_queue_age_seconds: int = 1800,
    event_count_threshold: int = 5,
) -> int:
    """Atomically append refresh intent and return the desired Insights revision."""
    if event_type not in EVENT_TYPES:
        raise ValueError("Unsupported clinical synthesis refresh event.")
    if not 0 <= debounce_seconds <= 900:
        raise ValueError("Refresh debounce must be between 0 and 900 seconds.")
    if not 60 <= maximum_queue_age_seconds <= 86_400:
        raise ValueError("Maximum queue age must be between 60 seconds and one day.")
    if not 1 <= event_count_threshold <= 100:
        raise ValueError("Refresh event threshold must be between 1 and 100.")
    effective_debounce_seconds = 0 if event_type in PROMPT_EVENT_TYPES else debounce_seconds

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (f"clinical-synthesis:{organization_id}:{client_id}",),
        )
        cursor.execute(
            """
            INSERT INTO app.clinical_synthesis_refresh_state AS state (
              organization_id, client_id, desired_insights_revision, status,
              pending_event_count, pending_since, not_before, last_event_at
            ) VALUES (
              %s, %s, 1, 'pending', 1, CURRENT_TIMESTAMP,
              CURRENT_TIMESTAMP + %s * INTERVAL '1 second', CURRENT_TIMESTAMP
            )
            ON CONFLICT (organization_id, client_id) DO UPDATE SET
              desired_insights_revision = state.desired_insights_revision + 1,
              status = CASE
                WHEN state.status = 'running' THEN 'running'
                ELSE 'pending'
              END,
              pending_event_count = state.pending_event_count + 1,
              pending_since = COALESCE(state.pending_since, CURRENT_TIMESTAMP),
              not_before = CASE
                WHEN state.pending_event_count + 1 >= %s THEN CURRENT_TIMESTAMP
                ELSE LEAST(
                  CURRENT_TIMESTAMP + %s * INTERVAL '1 second',
                  COALESCE(state.pending_since, CURRENT_TIMESTAMP)
                    + %s * INTERVAL '1 second'
                )
              END,
              last_event_at = CURRENT_TIMESTAMP,
              last_error_code = NULL,
              updated_at = CURRENT_TIMESTAMP
            RETURNING desired_insights_revision
            """,
            (
                organization_id,
                client_id,
                effective_debounce_seconds,
                event_count_threshold,
                effective_debounce_seconds,
                maximum_queue_age_seconds,
            ),
        )
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("Could not queue the Insights refresh.")
        revision = int(row["desired_insights_revision"])
        cursor.execute(
            """
            INSERT INTO app.clinical_synthesis_refresh_events (
              organization_id, client_id, desired_insights_revision, event_type,
              actor_user_id, target_type, target_id, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                organization_id,
                client_id,
                revision,
                event_type,
                actor_user_id,
                target_type,
                target_id,
                Json(dict(metadata or {})),
            ),
        )
    return revision


def claim_due_insights_refresh(
    connection: Any,
    *,
    worker_token: str,
    lease_seconds: int = 300,
) -> dict[str, Any] | None:
    """Lease one due client revision without allowing two workers to claim it."""
    if not worker_token.strip():
        raise ValueError("A worker token is required.")
    if not 30 <= lease_seconds <= 3600:
        raise ValueError("Worker leases must be between 30 seconds and one hour.")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH candidate AS (
              SELECT organization_id, client_id
              FROM app.clinical_synthesis_refresh_state
              WHERE desired_insights_revision > published_insights_revision
                AND not_before <= CURRENT_TIMESTAMP
                AND (
                  status = 'pending'
                  OR (status = 'running' AND lease_expires_at < CURRENT_TIMESTAMP)
                )
              ORDER BY pending_since NULLS LAST, last_event_at
              FOR UPDATE SKIP LOCKED
              LIMIT 1
            )
            UPDATE app.clinical_synthesis_refresh_state AS state
            SET status = 'running',
                processing_insights_revision = state.desired_insights_revision,
                worker_token = %s,
                lease_expires_at = CURRENT_TIMESTAMP + %s * INTERVAL '1 second',
                attempt_count = state.attempt_count + 1,
                last_attempt_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            FROM candidate
            WHERE state.organization_id = candidate.organization_id
              AND state.client_id = candidate.client_id
            RETURNING state.organization_id, state.client_id,
                      state.processing_insights_revision, state.pending_event_count,
                      state.attempt_count, state.worker_token
            """,
            (worker_token, lease_seconds),
        )
        return cursor.fetchone()


def next_appointment(
    connection: Any,
    *,
    organization_id: str,
    client_id: str,
) -> dict[str, Any] | None:
    """Return the appointment that should receive the next materialized brief."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, starts_at, ends_at
            FROM app.appointments
            WHERE organization_id = %s AND client_id = %s
              AND status IN ('scheduled', 'confirmed')
              AND ends_at > CURRENT_TIMESTAMP
            ORDER BY starts_at
            LIMIT 1
            """,
            (organization_id, client_id),
        )
        return cursor.fetchone()


def get_refresh_status(
    connection: Any,
    *,
    organization_id: str,
    client_id: str,
) -> dict[str, Any]:
    """Return non-clinical queue and freshness metadata for the workspace."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT state.status, state.desired_insights_revision,
                   state.published_insights_revision,
                   state.published_insight_snapshot_id,
                   state.pending_event_count, state.pending_since,
                   state.last_event_at, state.last_published_at,
                   state.last_error_code
            FROM app.clinical_synthesis_refresh_state AS state
            WHERE state.organization_id = %s AND state.client_id = %s
            """,
            (organization_id, client_id),
        )
        row = cursor.fetchone()
        if not row:
            cursor.execute(
                """
                SELECT id AS published_insight_snapshot_id, created_at AS last_published_at
                FROM app.longitudinal_insight_snapshots
                WHERE organization_id = %s AND client_id = %s AND status = 'accepted'
                ORDER BY version_number DESC LIMIT 1
                """,
                (organization_id, client_id),
            )
            snapshot = cursor.fetchone()
            row = {
                "status": "idle",
                "desired_insights_revision": 0,
                "published_insights_revision": 0,
                "published_insight_snapshot_id": snapshot["published_insight_snapshot_id"] if snapshot else None,
                "pending_event_count": 0,
                "pending_since": None,
                "last_event_at": None,
                "last_published_at": snapshot["last_published_at"] if snapshot else None,
                "last_error_code": None,
            }
    return {
        **row,
        "published_insight_snapshot_id": (
            str(row["published_insight_snapshot_id"])
            if row.get("published_insight_snapshot_id") else None
        ),
        "pending_since": row["pending_since"].isoformat() if row.get("pending_since") else None,
        "last_event_at": row["last_event_at"].isoformat() if row.get("last_event_at") else None,
        "last_published_at": row["last_published_at"].isoformat() if row.get("last_published_at") else None,
    }


def complete_synthesis_bundle(
    connection: Any,
    *,
    organization_id: str,
    client_id: str,
    worker_token: str,
    published_revision: int,
    insight_snapshot_id: str,
    appointment_id: str | None,
    brief_snapshot_id: str | None,
) -> None:
    """Atomically expose a validated Insights snapshot and its next brief.

    The caller must create both snapshot rows in this same transaction before
    invoking this function. A lost lease rolls the transaction back, so neither
    half of the generated pair becomes visible on its own.
    """
    if bool(appointment_id) != bool(brief_snapshot_id):
        raise ValueError("An appointment and brief snapshot must be published together.")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT desired_insights_revision, processing_insights_revision
            FROM app.clinical_synthesis_refresh_state
            WHERE organization_id = %s AND client_id = %s AND status = 'running'
              AND worker_token = %s
            FOR UPDATE
            """,
            (organization_id, client_id, worker_token),
        )
        state = cursor.fetchone()
        if not state or int(state["processing_insights_revision"]) != published_revision:
            raise ValueError("The Insights refresh lease is stale or no longer owned by this worker.")

        cursor.execute(
            """
            UPDATE app.longitudinal_insight_snapshots
            SET status = 'superseded'
            WHERE organization_id = %s AND client_id = %s AND status = 'accepted'
              AND id <> %s
            """,
            (organization_id, client_id, insight_snapshot_id),
        )
        if appointment_id and brief_snapshot_id:
            cursor.execute(
                """
                UPDATE app.pre_session_brief_snapshots
                SET status = 'superseded'
                WHERE organization_id = %s AND client_id = %s
                  AND appointment_id = %s AND status = 'accepted' AND id <> %s
                """,
                (organization_id, client_id, appointment_id, brief_snapshot_id),
            )

        cursor.execute(
            """
            UPDATE app.clinical_synthesis_refresh_events
            SET consumed_at = CURRENT_TIMESTAMP
            WHERE organization_id = %s AND client_id = %s
              AND desired_insights_revision <= %s AND consumed_at IS NULL
            """,
            (organization_id, client_id, published_revision),
        )
        still_pending = int(state["desired_insights_revision"]) > published_revision
        cursor.execute(
            """
            UPDATE app.clinical_synthesis_refresh_state
            SET published_insights_revision = %s,
                published_insight_snapshot_id = %s,
                processing_insights_revision = NULL,
                status = %s,
                pending_event_count = (
                  SELECT count(*) FROM app.clinical_synthesis_refresh_events
                  WHERE organization_id = %s AND client_id = %s AND consumed_at IS NULL
                ),
                pending_since = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END,
                not_before = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END,
                worker_token = NULL, lease_expires_at = NULL,
                attempt_count = 0, last_published_at = CURRENT_TIMESTAMP,
                last_error_code = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE organization_id = %s AND client_id = %s
            """,
            (
                published_revision, insight_snapshot_id,
                "pending" if still_pending else "idle",
                organization_id, client_id, still_pending, still_pending,
                organization_id, client_id,
            ),
        )
        if appointment_id and brief_snapshot_id:
            cursor.execute(
                """
                INSERT INTO app.pre_session_brief_refresh_state AS brief_state (
                  appointment_id, organization_id, client_id, source_insight_snapshot_id,
                  desired_insights_revision, published_insights_revision, status,
                  published_brief_snapshot_id, last_published_at, not_before
                ) VALUES (%s,%s,%s,%s,%s,%s,'idle',%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                ON CONFLICT (appointment_id) DO UPDATE SET
                  source_insight_snapshot_id = EXCLUDED.source_insight_snapshot_id,
                  desired_insights_revision = EXCLUDED.desired_insights_revision,
                  published_insights_revision = EXCLUDED.published_insights_revision,
                  status = 'idle', published_brief_snapshot_id = EXCLUDED.published_brief_snapshot_id,
                  last_published_at = CURRENT_TIMESTAMP, worker_token = NULL,
                  lease_expires_at = NULL, attempt_count = 0, last_error_code = NULL,
                  updated_at = CURRENT_TIMESTAMP
                """,
                (
                    appointment_id, organization_id, client_id, insight_snapshot_id,
                    published_revision, published_revision, brief_snapshot_id,
                ),
            )


def complete_insights_refresh(
    connection: Any,
    *,
    organization_id: str,
    client_id: str,
    worker_token: str,
    published_revision: int,
    insight_snapshot_id: str,
) -> None:
    """Publish one leased revision and queue the next appointment's brief."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT desired_insights_revision, processing_insights_revision
            FROM app.clinical_synthesis_refresh_state
            WHERE organization_id = %s AND client_id = %s AND status = 'running'
              AND worker_token = %s
            FOR UPDATE
            """,
            (organization_id, client_id, worker_token),
        )
        state = cursor.fetchone()
        if not state or int(state["processing_insights_revision"]) != published_revision:
            raise ValueError("The Insights refresh lease is stale or no longer owned by this worker.")
        cursor.execute(
            """
            UPDATE app.clinical_synthesis_refresh_events
            SET consumed_at = CURRENT_TIMESTAMP
            WHERE organization_id = %s AND client_id = %s
              AND desired_insights_revision <= %s AND consumed_at IS NULL
            """,
            (organization_id, client_id, published_revision),
        )
        still_pending = int(state["desired_insights_revision"]) > published_revision
        cursor.execute(
            """
            UPDATE app.clinical_synthesis_refresh_state
            SET published_insights_revision = %s,
                published_insight_snapshot_id = %s,
                processing_insights_revision = NULL,
                status = %s,
                pending_event_count = (
                  SELECT count(*) FROM app.clinical_synthesis_refresh_events
                  WHERE organization_id = %s AND client_id = %s AND consumed_at IS NULL
                ),
                pending_since = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END,
                not_before = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END,
                worker_token = NULL,
                lease_expires_at = NULL,
                attempt_count = 0,
                last_published_at = CURRENT_TIMESTAMP,
                last_error_code = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE organization_id = %s AND client_id = %s
            """,
            (
                published_revision,
                insight_snapshot_id,
                "pending" if still_pending else "idle",
                organization_id,
                client_id,
                still_pending,
                still_pending,
                organization_id,
                client_id,
            ),
        )
    enqueue_next_appointment_brief(
        connection,
        organization_id=organization_id,
        client_id=client_id,
    )


def fail_insights_refresh(
    connection: Any,
    *,
    organization_id: str,
    client_id: str,
    worker_token: str,
    error_code: str,
    retry_after_seconds: int = 300,
    maximum_attempts: int = 3,
) -> bool:
    """Release a failed lease. Return True when another retry remains scheduled."""
    if not error_code.strip():
        raise ValueError("A non-sensitive error code is required.")
    if maximum_attempts < 1:
        raise ValueError("Maximum attempts must be at least one.")
    if not 30 <= retry_after_seconds <= 86_400:
        raise ValueError("Retry delay must be between 30 seconds and one day.")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE app.clinical_synthesis_refresh_state
            SET status = CASE WHEN attempt_count < %s THEN 'pending' ELSE 'failed' END,
                processing_insights_revision = NULL,
                worker_token = NULL,
                lease_expires_at = NULL,
                not_before = CURRENT_TIMESTAMP + %s * INTERVAL '1 second',
                last_error_code = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE organization_id = %s AND client_id = %s
              AND status = 'running' AND worker_token = %s
            RETURNING status
            """,
            (
                maximum_attempts,
                retry_after_seconds,
                error_code,
                organization_id,
                client_id,
                worker_token,
            ),
        )
        row = cursor.fetchone()
    if not row:
        raise ValueError("The Insights refresh lease is stale or no longer owned by this worker.")
    return row["status"] == "pending"


def reconcile_refresh_queue(connection: Any) -> int:
    """Repair pending revision drift and expired worker leases without regenerating unchanged clients."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE app.clinical_synthesis_refresh_state
            SET status = 'pending',
                processing_insights_revision = NULL,
                worker_token = NULL,
                lease_expires_at = NULL,
                pending_since = COALESCE(pending_since, CURRENT_TIMESTAMP),
                not_before = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE desired_insights_revision > published_insights_revision
              AND (
                status = 'idle'
                OR (status = 'running' AND lease_expires_at < CURRENT_TIMESTAMP)
              )
            """
        )
        return int(cursor.rowcount)
