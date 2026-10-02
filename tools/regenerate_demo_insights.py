"""Regenerate the synthetic Elena longitudinal draft through a frontier model."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from ai_harness.longitudinal_insights import generate_openai_longitudinal_insights, to_snapshot_content
from database.connection import connect
from database.longitudinal_records import InsightEvidence, InsightItem, LongitudinalRecordRepository
from tools.migrate_heartwell_case import _context, _session_id


def _evidence(context: dict[str, str]) -> list[dict[str, object]]:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            WITH ranked AS (
              SELECT segment.id, segment.sequence_number, segment.content,
                     segment.starts_at_seconds, segment.ends_at_seconds,
                     session.id AS session_id, session.started_at,
                     COALESCE(job.storage->>'label', 'Completed session') AS session_label,
                     row_number() OVER (
                       PARTITION BY session.id
                       ORDER BY length(segment.content) DESC, segment.sequence_number
                     ) AS relevance_rank
              FROM app.transcript_segments segment
              JOIN app.transcript_versions transcript ON transcript.id=segment.transcript_version_id
              JOIN app.sessions session ON session.id=transcript.session_id
              LEFT JOIN app.session_storage_jobs job ON job.session_id=session.id
              WHERE transcript.organization_id=%s AND transcript.client_id=%s
                AND session.status IN ('review', 'finalized')
                AND segment.speaker_label='PATIENT_0'
                AND length(trim(segment.content)) >= 20
            )
            SELECT * FROM ranked WHERE relevance_rank <= 24
            ORDER BY started_at, sequence_number
            """,
            (context["organization_id"], context["client_id"]),
        )
        rows = cursor.fetchall()
    return [{
        "evidence_id": str(row["id"]),
        "session_id": str(row["session_id"]),
        "session_label": row["session_label"],
        "session_started_at": row["started_at"].isoformat(),
        "segment_index": row["sequence_number"],
        "start": float(row["starts_at_seconds"]),
        "end": float(row["ends_at_seconds"]),
        "quote": row["content"],
    } for row in rows]


def main() -> None:
    load_dotenv(ROOT / ".env", override=True)
    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("INSIGHTS_MODEL", "gpt-5")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    context = _context()
    evidence = _evidence(context)
    if not evidence:
        raise RuntimeError("No eligible transcript evidence was selected; generation was not attempted.")
    alias_to_id = {f"E{index:03d}": source["evidence_id"] for index, source in enumerate(evidence, 1)}
    model_evidence = [
        {**source, "evidence_id": alias}
        for alias, source in zip(alias_to_id, evidence, strict=True)
    ]
    generated_batches = []
    metadata_batches = []
    for kind in ("trajectory", "theme", "open_thread", "relevant_history"):
        generated_batch, metadata = generate_openai_longitudinal_insights(
            evidence=model_evidence, api_key=api_key, model=model, kind=kind,
        )
        generated_batches.append(generated_batch)
        metadata_batches.append(metadata)
    generated = {
        "overview": generated_batches[0]["overview"],
        "items": [item for batch in generated_batches for item in batch["items"]],
    }
    snapshot_content, generated_items = to_snapshot_content(generated)
    for item in generated_items:
        item["evidence_ids"] = [alias_to_id[value] for value in item["evidence_ids"]]
        for contextual_statement in item["content"]["contexts"]:
            for claim in contextual_statement["claims"]:
                claim["evidence_ids"] = [alias_to_id[value] for value in claim["evidence_ids"]]
    evidence_by_id = {source["evidence_id"]: source for source in evidence}
    items = tuple(
        InsightItem(
            item_kind=item["kind"],
            content=item["content"],
            evidence=tuple(InsightEvidence(transcript_segment_id=evidence_id) for evidence_id in item["evidence_ids"]),
            review_state="draft",
            display_order=index,
        )
        for index, item in enumerate(generated_items)
    )
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id FROM app.longitudinal_insight_snapshots
                   WHERE organization_id=%s AND client_id=%s ORDER BY version_number DESC LIMIT 1""",
                (context["organization_id"], context["client_id"]),
            )
            previous = cursor.fetchone()
        snapshot_id = LongitudinalRecordRepository(connection).create_insight_snapshot(
            organization_id=context["organization_id"],
            client_id=context["client_id"],
            content={
                **snapshot_content,
                "review_note": "Frontier-model draft. Review analysis and linked record context before accepting.",
                "provider_response_ids": [metadata["response_id"] for metadata in metadata_batches],
            },
            items=items,
            generator_name="OpenAI frontier longitudinal synthesis",
            generator_version=metadata_batches[0]["model"],
            selection_policy_version="synthetic-completed-transcripts-v1",
            actor_user_id=context["actor_user_id"],
            status="draft",
            source_cutoff_session_id=_session_id(6),
            parent_snapshot_id=str(previous["id"]) if previous else None,
        )
    print(json.dumps({
        "snapshot_id": snapshot_id,
        "model": metadata_batches[0]["model"],
        "item_count": len(items),
        "evidence_count": len(evidence_by_id),
        "usage": [metadata["usage"] for metadata in metadata_batches],
    }, indent=2))


if __name__ == "__main__":
    main()
