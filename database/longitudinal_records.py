"""Persistence boundary for reviewable clinical-note and longitudinal records.

This module deliberately requires explicit organization, client, and actor IDs.
It does not infer identity from a recording job or allow a model provider to
write directly to the clinical record.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from psycopg import Connection
from psycopg.types.json import Json


@dataclass(frozen=True)
class InsightEvidence:
    """One inspectable source supporting or contextualizing an insight item."""

    transcript_segment_id: str | None = None
    clinical_note_version_id: str | None = None
    evidence_role: str = "supporting"

    def validate(self) -> None:
        if not self.transcript_segment_id and not self.clinical_note_version_id:
            raise ValueError("Insight evidence must reference a transcript segment or clinical note version.")
        if self.evidence_role not in {"supporting", "contrasting", "context"}:
            raise ValueError("Insight evidence has an unsupported role.")


@dataclass(frozen=True)
class InsightItem:
    """A reviewable item in a longitudinal insight snapshot."""

    item_kind: str
    content: Mapping[str, Any]
    evidence: tuple[InsightEvidence, ...]
    review_state: str = "draft"
    display_order: int = 0

    def validate(self) -> None:
        if self.item_kind not in {"trajectory", "theme", "open_thread", "relevant_history", "client_context", "therapist_curated"}:
            raise ValueError("Insight item has an unsupported kind.")
        if self.review_state not in {"draft", "accepted", "hidden", "stale", "disputed"}:
            raise ValueError("Insight item has an unsupported review state.")
        if not self.content:
            raise ValueError("Insight item content cannot be empty.")
        if not self.evidence:
            raise ValueError("Insight items require at least one reviewable source.")
        for evidence in self.evidence:
            evidence.validate()


class LongitudinalRecordRepository:
    """Versioned writes and source-bounded reads for the longitudinal record."""

    def __init__(self, connection: Connection[Any]):
        self.connection = connection

    @staticmethod
    def _assert_session_scope(
        cursor: Any,
        *,
        organization_id: str,
        client_id: str,
        session_id: str,
    ) -> None:
        """Ensure a note revision cannot be attached across client boundaries."""
        cursor.execute(
            """
            SELECT 1
            FROM app.sessions
            WHERE id = %s AND organization_id = %s AND client_id = %s
            """,
            (session_id, organization_id, client_id),
        )
        if not cursor.fetchone():
            raise ValueError("The session is not available for this client and organization.")

    @staticmethod
    def _assert_evidence_scope(
        cursor: Any,
        *,
        organization_id: str,
        client_id: str,
        evidence: InsightEvidence,
    ) -> None:
        """Require every cited source to belong to the snapshot's client."""
        if evidence.transcript_segment_id:
            cursor.execute(
                """
                SELECT 1
                FROM app.transcript_segments AS segment
                JOIN app.transcript_versions AS transcript
                  ON transcript.id = segment.transcript_version_id
                WHERE segment.id = %s
                  AND transcript.organization_id = %s
                  AND transcript.client_id = %s
                """,
                (evidence.transcript_segment_id, organization_id, client_id),
            )
            if not cursor.fetchone():
                raise ValueError("Transcript evidence is not available for this client and organization.")
        if evidence.clinical_note_version_id:
            cursor.execute(
                """
                SELECT 1
                FROM app.clinical_note_versions
                WHERE id = %s AND organization_id = %s AND client_id = %s
                """,
                (evidence.clinical_note_version_id, organization_id, client_id),
            )
            if not cursor.fetchone():
                raise ValueError("Clinical-note evidence is not available for this client and organization.")

    def create_clinical_note_version(
        self,
        *,
        organization_id: str,
        client_id: str,
        session_id: str,
        content: Mapping[str, Any],
        status: str,
        actor_user_id: str,
        source_synthesis_version_id: str | None = None,
        parent_version_id: str | None = None,
    ) -> str:
        """Append, never overwrite, a clinician-owned note revision."""
        if status not in {"draft", "reviewed", "finalized"}:
            raise ValueError("Clinical-note status must be draft, reviewed, or finalized.")
        if not content:
            raise ValueError("Clinical-note content cannot be empty.")
        with self.connection.cursor() as cursor:
            self._assert_session_scope(
                cursor,
                organization_id=organization_id,
                client_id=client_id,
                session_id=session_id,
            )
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (session_id,))
            cursor.execute(
                """
                SELECT version_number
                FROM app.clinical_note_versions
                WHERE session_id = %s
                ORDER BY version_number DESC
                LIMIT 1
                FOR UPDATE
                """,
                (session_id,),
            )
            previous = cursor.fetchone()
            version_number = (previous["version_number"] if previous else 0) + 1
            cursor.execute(
                """
                INSERT INTO app.clinical_note_versions (
                  organization_id, client_id, session_id, parent_version_id,
                  source_synthesis_version_id, version_number, status, content,
                  authored_by_user_id, finalized_by_user_id, finalized_at
                ) VALUES (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s,
                  CASE WHEN %s = 'finalized' THEN %s ELSE NULL END,
                  CASE WHEN %s = 'finalized' THEN CURRENT_TIMESTAMP ELSE NULL END
                ) RETURNING id
                """,
                (
                    organization_id, client_id, session_id, parent_version_id,
                    source_synthesis_version_id, version_number, status, Json(dict(content)), actor_user_id,
                    status, actor_user_id, status,
                ),
            )
            row = cursor.fetchone()
            if not row:
                raise RuntimeError("Could not persist the clinical-note version.")
            return str(row["id"])

    def create_insight_snapshot(
        self,
        *,
        organization_id: str,
        client_id: str,
        content: Mapping[str, Any],
        items: Iterable[InsightItem],
        generator_name: str,
        selection_policy_version: str,
        actor_user_id: str,
        status: str = "draft",
        generator_version: str | None = None,
        source_cutoff_session_id: str | None = None,
        parent_snapshot_id: str | None = None,
    ) -> str:
        """Append a source-linked insight snapshot and all of its items atomically."""
        if status not in {"draft", "reviewed", "accepted", "rejected"}:
            raise ValueError("Insight-snapshot status is unsupported.")
        if not content:
            raise ValueError("Insight-snapshot content cannot be empty.")
        materialized_items = tuple(items)
        for item in materialized_items:
            item.validate()

        with self.connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (client_id,))
            cursor.execute(
                """
                SELECT version_number
                FROM app.longitudinal_insight_snapshots
                WHERE client_id = %s
                ORDER BY version_number DESC
                LIMIT 1
                FOR UPDATE
                """,
                (client_id,),
            )
            previous = cursor.fetchone()
            version_number = (previous["version_number"] if previous else 0) + 1
            cursor.execute(
                """
                INSERT INTO app.longitudinal_insight_snapshots (
                  organization_id, client_id, parent_snapshot_id, source_cutoff_session_id,
                  version_number, status, generator_name, generator_version,
                  selection_policy_version, content, created_by_user_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (organization_id, client_id, parent_snapshot_id, source_cutoff_session_id, version_number,
                 status, generator_name, generator_version, selection_policy_version, Json(dict(content)), actor_user_id),
            )
            snapshot = cursor.fetchone()
            if not snapshot:
                raise RuntimeError("Could not persist the longitudinal insight snapshot.")
            snapshot_id = str(snapshot["id"])

            for item in materialized_items:
                for evidence in item.evidence:
                    self._assert_evidence_scope(
                        cursor,
                        organization_id=organization_id,
                        client_id=client_id,
                        evidence=evidence,
                    )
                cursor.execute(
                    """
                    INSERT INTO app.longitudinal_insight_items (
                      snapshot_id, item_kind, review_state, display_order, content
                    ) VALUES (%s, %s, %s, %s, %s) RETURNING id
                    """,
                    (snapshot_id, item.item_kind, item.review_state, item.display_order, Json(dict(item.content))),
                )
                persisted_item = cursor.fetchone()
                if not persisted_item:
                    raise RuntimeError("Could not persist a longitudinal insight item.")
                for evidence in item.evidence:
                    cursor.execute(
                        """
                        INSERT INTO app.longitudinal_insight_evidence (
                          insight_item_id, transcript_segment_id, clinical_note_version_id, evidence_role
                        ) VALUES (%s, %s, %s, %s)
                        """,
                        (str(persisted_item["id"]), evidence.transcript_segment_id, evidence.clinical_note_version_id, evidence.evidence_role),
                    )
            return snapshot_id

    def build_pre_session_context_packet(self, *, organization_id: str, client_id: str, limit: int = 12) -> dict[str, Any] | None:
        """Build a bounded packet from the latest accepted snapshot only.

        Hidden, stale, disputed, and draft items are intentionally omitted. This
        method selects application-owned records; it does not call a model.
        """
        if limit < 1 or limit > 30:
            raise ValueError("Context-packet limit must be between 1 and 30.")
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, version_number, selection_policy_version, content
                FROM app.longitudinal_insight_snapshots
                WHERE organization_id = %s AND client_id = %s AND status = 'accepted'
                ORDER BY version_number DESC
                LIMIT 1
                """,
                (organization_id, client_id),
            )
            snapshot = cursor.fetchone()
            if not snapshot:
                return None
            cursor.execute(
                """
                WITH selected_items AS (
                  SELECT id, item_kind, content, display_order
                  FROM app.longitudinal_insight_items
                  WHERE snapshot_id = %s AND review_state = 'accepted'
                  ORDER BY display_order, id
                  LIMIT %s
                )
                SELECT item.id, item.item_kind, item.content, item.display_order,
                       evidence.evidence_role, segment.id AS transcript_segment_id,
                       segment.sequence_number, segment.starts_at_seconds,
                       segment.ends_at_seconds, segment.content AS transcript_quote,
                       session.id AS session_id, session.started_at,
                       note.id AS clinical_note_version_id
                FROM selected_items AS item
                LEFT JOIN app.longitudinal_insight_evidence AS evidence ON evidence.insight_item_id = item.id
                LEFT JOIN app.transcript_segments AS segment ON segment.id = evidence.transcript_segment_id
                LEFT JOIN app.transcript_versions AS transcript ON transcript.id = segment.transcript_version_id
                LEFT JOIN app.sessions AS session ON session.id = transcript.session_id
                LEFT JOIN app.clinical_note_versions AS note ON note.id = evidence.clinical_note_version_id
                ORDER BY item.display_order, item.id, evidence.created_at
                """,
                (snapshot["id"], limit),
            )
            rows = cursor.fetchall()

        items: dict[str, dict[str, Any]] = {}
        for row in rows:
            item_id = str(row["id"])
            item = items.setdefault(item_id, {
                "kind": row["item_kind"], "content": row["content"], "evidence": [],
            })
            if row["transcript_segment_id"]:
                item["evidence"].append({
                    "evidence_role": row["evidence_role"],
                    "transcript_segment_id": str(row["transcript_segment_id"]),
                    "session_id": str(row["session_id"]),
                    "segment_index": row["sequence_number"],
                    "start": float(row["starts_at_seconds"]),
                    "end": float(row["ends_at_seconds"]),
                    "quote": row["transcript_quote"],
                })
            elif row["clinical_note_version_id"]:
                item["evidence"].append({
                    "evidence_role": row["evidence_role"],
                    "clinical_note_version_id": str(row["clinical_note_version_id"]),
                })

        return {
            "snapshot_id": str(snapshot["id"]),
            "snapshot_version": snapshot["version_number"],
            "selection_policy_version": snapshot["selection_policy_version"],
            "snapshot_summary": snapshot["content"],
            "items": list(items.values()),
        }

    def get_latest_insight_snapshot(self, *, organization_id: str, client_id: str) -> dict[str, Any] | None:
        """Read the newest review workspace with its source lineage intact."""
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, version_number, status, generator_name, generator_version,
                       selection_policy_version, content, created_at, reviewed_at
                FROM app.longitudinal_insight_snapshots
                WHERE organization_id = %s AND client_id = %s
                ORDER BY version_number DESC
                LIMIT 1
                """,
                (organization_id, client_id),
            )
            snapshot = cursor.fetchone()
            if not snapshot:
                return None
            cursor.execute(
                """
                SELECT item.id, item.item_kind, item.review_state, item.display_order,
                       item.content, evidence.evidence_role,
                       segment.id AS transcript_segment_id, segment.sequence_number,
                       segment.starts_at_seconds, segment.ends_at_seconds,
                       segment.content AS transcript_quote, session.id AS session_id,
                       session.started_at, note.id AS clinical_note_version_id
                FROM app.longitudinal_insight_items AS item
                LEFT JOIN app.longitudinal_insight_evidence AS evidence
                  ON evidence.insight_item_id = item.id
                LEFT JOIN app.transcript_segments AS segment
                  ON segment.id = evidence.transcript_segment_id
                LEFT JOIN app.transcript_versions AS transcript
                  ON transcript.id = segment.transcript_version_id
                LEFT JOIN app.sessions AS session ON session.id = transcript.session_id
                LEFT JOIN app.clinical_note_versions AS note
                  ON note.id = evidence.clinical_note_version_id
                WHERE item.snapshot_id = %s
                ORDER BY item.display_order, item.id, evidence.created_at
                """,
                (snapshot["id"],),
            )
            rows = cursor.fetchall()

        items: dict[str, dict[str, Any]] = {}
        for row in rows:
            item_id = str(row["id"])
            item = items.setdefault(item_id, {
                "id": item_id,
                "kind": row["item_kind"],
                "review_state": row["review_state"],
                "display_order": row["display_order"],
                "content": row["content"],
                "evidence": [],
            })
            if row["transcript_segment_id"]:
                item["evidence"].append({
                    "evidence_role": row["evidence_role"],
                    "transcript_segment_id": str(row["transcript_segment_id"]),
                    "session_id": str(row["session_id"]),
                    "segment_index": row["sequence_number"],
                    "start": float(row["starts_at_seconds"]),
                    "end": float(row["ends_at_seconds"]),
                    "quote": row["transcript_quote"],
                })
            elif row["clinical_note_version_id"]:
                item["evidence"].append({
                    "evidence_role": row["evidence_role"],
                    "clinical_note_version_id": str(row["clinical_note_version_id"]),
                })

        return {
            "id": str(snapshot["id"]),
            "version": snapshot["version_number"],
            "status": snapshot["status"],
            "generator_name": snapshot["generator_name"],
            "generator_version": snapshot["generator_version"],
            "selection_policy_version": snapshot["selection_policy_version"],
            "content": snapshot["content"],
            "created_at": snapshot["created_at"].isoformat(),
            "reviewed_at": snapshot["reviewed_at"].isoformat() if snapshot["reviewed_at"] else None,
            "items": list(items.values()),
        }

    def create_pre_session_brief_snapshot(
        self,
        *,
        organization_id: str,
        client_id: str,
        context_packet: Mapping[str, Any],
        content: Mapping[str, Any],
        generator_name: str,
        status: str = "draft",
        generator_version: str | None = None,
        upcoming_session_id: str | None = None,
        source_insight_snapshot_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> str:
        """Save the exact packet and generated draft for later clinical review."""
        if status not in {"draft", "reviewed", "accepted", "discarded"}:
            raise ValueError("Pre-session-brief status is unsupported.")
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO app.pre_session_brief_snapshots (
                  organization_id, client_id, upcoming_session_id, source_insight_snapshot_id,
                  status, generator_name, generator_version, context_packet, content, created_by_user_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (organization_id, client_id, upcoming_session_id, source_insight_snapshot_id, status,
                 generator_name, generator_version, Json(dict(context_packet)), Json(dict(content)), actor_user_id),
            )
            row = cursor.fetchone()
            if not row:
                raise RuntimeError("Could not persist the pre-session brief snapshot.")
            return str(row["id"])
