"""Leased worker for atomic Insights and pre-session-brief publication."""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from ai_harness.brief_projection import project_accepted_insights
from ai_harness.brief_service import brief_input
from ai_harness.longitudinal_insights import generate_openai_longitudinal_insights, to_snapshot_content
from ai_harness.pre_session import generate_openai_pre_session_brief, resolve_brief
from database import client_journey, synthesis_refresh
from database.connection import connect
from database.longitudinal_records import InsightEvidence, InsightItem, LongitudinalRecordRepository


INSIGHT_KINDS = ("trajectory", "theme", "open_thread", "relevant_history")


def _accepted_evidence(connection: Any, organization_id: str, client_id: str) -> list[dict[str, Any]]:
    """Flatten therapist-accepted claims into a bounded, source-linked bundle."""
    entries = client_journey.list_entries(connection, organization_id, client_id, status="accepted")
    sources: dict[str, dict[str, Any]] = {}
    for entry in entries:
        for source in entry["evidence"]:
            evidence_id = source["evidence_id"]
            selected = sources.setdefault(evidence_id, {**source, "accepted_guidance": [], "categories": []})
            if entry["text"] not in selected["accepted_guidance"]:
                selected["accepted_guidance"].append(entry["text"])
            selected["categories"] = list(dict.fromkeys([*selected["categories"], *entry["categories"]]))
    ordered = sorted(
        sources.values(),
        key=lambda source: (source.get("session_label", ""), source.get("segment_index", 0), source["evidence_id"]),
    )
    # Bound provider input without severing any selected source from its exact ID.
    return ordered[-120:]


def _input_fingerprint(evidence: list[dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _generate_bundle(
    evidence: list[dict[str, Any]],
    *,
    insights_model: str,
    brief_model: str,
    insight_generator: Callable[..., tuple[dict[str, Any], dict[str, Any]]] = generate_openai_longitudinal_insights,
    brief_generator: Callable[..., tuple[dict[str, Any], dict[str, Any]]] = generate_openai_pre_session_brief,
) -> dict[str, Any]:
    aliases = {f"E{index:03d}": source["evidence_id"] for index, source in enumerate(evidence, 1)}
    model_evidence = [
        {**source, "evidence_id": alias}
        for alias, source in zip(aliases, evidence, strict=True)
    ]
    batches: list[dict[str, Any]] = []
    insight_metadata: list[dict[str, Any]] = []
    for kind in INSIGHT_KINDS:
        generated, metadata = insight_generator(
            evidence=model_evidence,
            api_key=os.environ["OPENAI_API_KEY"],
            model=insights_model,
            kind=kind,
        )
        batches.append(generated)
        insight_metadata.append(metadata)
    combined = {
        "overview": batches[0]["overview"],
        "items": [item for batch in batches for item in batch["items"]],
    }
    snapshot_content, generated_items = to_snapshot_content(combined)
    for item in generated_items:
        item["evidence_ids"] = [aliases[value] for value in item["evidence_ids"]]
        for context in item["content"]["contexts"]:
            for claim in context["claims"]:
                claim["evidence_ids"] = [aliases[value] for value in claim["evidence_ids"]]

    evidence_by_id = {source["evidence_id"]: source for source in evidence}
    packet = {
        "snapshot_id": "pending-publication",
        "snapshot_version": 0,
        "items": [
            {
                "kind": item["kind"],
                "content": item["content"],
                "evidence": [
                    {
                        "evidence_role": "supporting",
                        "transcript_segment_id": evidence_id,
                        "session_id": evidence_by_id[evidence_id]["session_id"].removeprefix("session-"),
                        "session_label": evidence_by_id[evidence_id]["session_label"],
                        "segment_index": evidence_by_id[evidence_id].get("segment_index"),
                        "start": evidence_by_id[evidence_id].get("start"),
                        "end": evidence_by_id[evidence_id].get("end"),
                        "quote": evidence_by_id[evidence_id].get("quote"),
                    }
                    for evidence_id in item["evidence_ids"]
                ],
            }
            for item in generated_items
        ],
    }
    projected = project_accepted_insights(packet, [])
    _, request = brief_input(projected)
    brief_response, brief_metadata = brief_generator(
        synthesis_request=request,
        api_key=os.environ["OPENAI_API_KEY"],
        model=brief_model,
    )
    resolved_brief = resolve_brief(brief_response, request["evidence"])
    return {
        "snapshot_content": {
            **snapshot_content,
            "review_note": "Generated review workspace. Verify linked evidence before relying on observations.",
            "input_fingerprint": _input_fingerprint(evidence),
        },
        "generated_items": generated_items,
        "packet": packet,
        "brief": resolved_brief,
        "insights_model": insight_metadata[0].get("model", insights_model),
        "brief_model": brief_metadata.get("model", brief_model),
    }


def process_one() -> bool:
    """Process one due revision. Return False when no work is currently due."""
    worker_token = str(uuid4())
    with connect() as connection:
        job = synthesis_refresh.claim_due_insights_refresh(connection, worker_token=worker_token, lease_seconds=1800)
    if not job:
        return False

    organization_id = str(job["organization_id"])
    client_id = str(job["client_id"])
    revision = int(job["processing_insights_revision"])
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        insights_model = os.getenv("INSIGHTS_MODEL")
        brief_model = os.getenv("PRE_SESSION_MODEL")
        if not api_key or not insights_model or not brief_model:
            raise RuntimeError("synthesis_provider_not_configured")

        with connect() as connection:
            evidence = _accepted_evidence(connection, organization_id, client_id)
            appointment = synthesis_refresh.next_appointment(
                connection, organization_id=organization_id, client_id=client_id,
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT id FROM app.longitudinal_insight_snapshots
                       WHERE organization_id=%s AND client_id=%s AND status='accepted'
                       ORDER BY version_number DESC LIMIT 1""",
                    (organization_id, client_id),
                )
                previous = cursor.fetchone()
                cursor.execute(
                    """SELECT actor_user_id FROM app.clinical_synthesis_refresh_events
                       WHERE organization_id=%s AND client_id=%s
                         AND desired_insights_revision <= %s AND actor_user_id IS NOT NULL
                       ORDER BY created_at DESC LIMIT 1""",
                    (organization_id, client_id, revision),
                )
                actor = cursor.fetchone()
        if not evidence:
            raise RuntimeError("no_accepted_source_evidence")

        bundle = _generate_bundle(
            evidence,
            insights_model=insights_model,
            brief_model=brief_model,
        )
        evidence_ids = {source["evidence_id"] for source in evidence}
        items = tuple(
            InsightItem(
                item_kind=item["kind"],
                content=item["content"],
                evidence=tuple(
                    InsightEvidence(transcript_segment_id=evidence_id)
                    for evidence_id in item["evidence_ids"] if evidence_id in evidence_ids
                ),
                review_state="draft",
                display_order=index,
            )
            for index, item in enumerate(bundle["generated_items"])
        )
        actor_user_id = str(actor["actor_user_id"]) if actor else None
        with connect() as connection:
            repository = LongitudinalRecordRepository(connection)
            snapshot_id = repository.create_insight_snapshot(
                organization_id=organization_id,
                client_id=client_id,
                content=bundle["snapshot_content"],
                items=items,
                generator_name="Queued longitudinal synthesis",
                generator_version=bundle["insights_model"],
                selection_policy_version="accepted-evidence-v1",
                actor_user_id=actor_user_id,
                status="accepted",
                parent_snapshot_id=str(previous["id"]) if previous else None,
            )
            appointment_id = str(appointment["id"]) if appointment else None
            brief_id = repository.create_pre_session_brief_snapshot(
                organization_id=organization_id,
                client_id=client_id,
                context_packet={**bundle["packet"], "snapshot_id": snapshot_id},
                content=bundle["brief"],
                generator_name="Queued pre-session editorial synthesis",
                generator_version=bundle["brief_model"],
                status="accepted",
                appointment_id=appointment_id,
                source_insight_snapshot_id=snapshot_id,
                actor_user_id=actor_user_id,
            ) if appointment_id else None
            synthesis_refresh.complete_synthesis_bundle(
                connection,
                organization_id=organization_id,
                client_id=client_id,
                worker_token=worker_token,
                published_revision=revision,
                insight_snapshot_id=snapshot_id,
                appointment_id=appointment_id,
                brief_snapshot_id=brief_id,
            )
        return True
    except Exception as exc:
        if isinstance(exc, RuntimeError) and str(exc) in {
            "synthesis_provider_not_configured", "no_accepted_source_evidence",
        }:
            error_code = str(exc)
        else:
            error_code = "synthesis_generation_failed"
        with connect() as connection:
            synthesis_refresh.fail_insights_refresh(
                connection,
                organization_id=organization_id,
                client_id=client_id,
                worker_token=worker_token,
                error_code=error_code,
                retry_after_seconds=300,
            )
        return True
