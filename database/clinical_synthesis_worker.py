"""Leased worker for atomic Insights and pre-session-brief publication."""
from __future__ import annotations

import hashlib
import json
import os
import logging
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from ai_harness.brief_projection import project_accepted_insights
from ai_harness.brief_service import brief_input
from ai_harness.clinical_context import alias_context_sources
from ai_harness.longitudinal_insights import INSIGHTS_GENERATOR_VERSION, generate_openai_longitudinal_insights, to_snapshot_content
from ai_harness.pre_session import generate_openai_pre_session_brief, resolve_brief
from database import synthesis_refresh
from database import client_diagnostics
from database.clinical_context import build_clinical_context, fingerprint
from database.connection import connect
from database.longitudinal_records import InsightEvidence, InsightItem, LongitudinalRecordRepository

LOGGER = logging.getLogger(__name__)




def _accepted_evidence(connection: Any, organization_id: str, client_id: str) -> list[dict[str, Any]]:
    """Compatibility helper: use the same eligible sources as discovery."""
    return build_clinical_context(connection, organization_id=organization_id,
                                  client_id=client_id)['source_evidence']


def _input_fingerprint(evidence: list[dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _generate_bundle(
    evidence: list[dict[str, Any]],
    *,
    clinical_context: dict[str, Any] | None = None,
    insights_model: str,
    brief_model: str,
    insight_generator: Callable[..., tuple[dict[str, Any], dict[str, Any]]] = generate_openai_longitudinal_insights,
    brief_generator: Callable[..., tuple[dict[str, Any], dict[str, Any]]] = generate_openai_pre_session_brief,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    def emit(event_type, **details):
        if on_event:
            on_event(event_type, details)

    aliases = {f"E{index:03d}": source["evidence_id"] for index, source in enumerate(evidence, 1)}
    model_evidence = [
        {**source, "evidence_id": alias}
        for alias, source in zip(aliases, evidence, strict=True)
    ]
    emit('insights_requested', stage='insights')
    repair_options = {'on_repair': lambda attempt, count: emit('insights_repair_requested',
        stage='insights', repair_attempt=attempt, violation_count=count)} if on_event and insight_generator is generate_openai_longitudinal_insights else {}
    generated, insight_metadata = insight_generator(
        evidence=model_evidence,
        clinical_context=alias_context_sources(clinical_context, {value: key for key, value in aliases.items()}),
        api_key=os.environ["OPENAI_API_KEY"],
        model=insights_model,
        **repair_options,
    )
    usage = insight_metadata.get('usage') or {}
    emit('insights_validated', stage='insights', input_tokens=usage.get('input_tokens'), output_tokens=usage.get('output_tokens'))
    snapshot_content, generated_items = to_snapshot_content(generated)
    for item in generated_items:
        item["evidence_ids"] = [aliases[value] for value in item["evidence_ids"]]
        for claim in item["content"].get("analysis_claims", []):
            claim["evidence_ids"] = [aliases[value] for value in claim["evidence_ids"]]
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
                        "transcript_segment_id": evidence_id if evidence_by_id[evidence_id].get("source_type") != "finalized_clinical_note" else None,
                        "clinical_note_version_id": evidence_by_id[evidence_id].get("clinical_note_version_id"),
                        "note_text": (evidence_by_id[evidence_id].get("content") or {}).get("plain_text") or json.dumps(evidence_by_id[evidence_id].get("content") or {}, ensure_ascii=False),
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
    emit('brief_requested', stage='brief')
    projected = project_accepted_insights(packet, [])
    _, request = brief_input(projected)
    brief_response, brief_metadata = brief_generator(
        synthesis_request=request,
        api_key=os.environ["OPENAI_API_KEY"],
        model=brief_model,
    )
    resolved_brief = resolve_brief(brief_response, request["evidence"])
    usage = brief_metadata.get('usage') or {}
    emit('brief_validated', stage='brief', input_tokens=usage.get('input_tokens'), output_tokens=usage.get('output_tokens'))
    return {
        "snapshot_content": {
            **snapshot_content,
            "review_note": "Generated review workspace. Verify linked evidence before relying on observations.",
            "input_fingerprint": fingerprint(clinical_context) if clinical_context else _input_fingerprint(evidence),
            "generator_version": insight_metadata.get("generator_version", INSIGHTS_GENERATOR_VERSION),
            "context_policy_version": (clinical_context or {}).get("policy_version"),
        },
        "generated_items": generated_items,
        "packet": packet,
        "brief": resolved_brief,
        "insights_model": insight_metadata.get("model", insights_model),
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
    stage = 'context'

    def record(event_type, details):
        nonlocal stage
        stage = details.get('stage', stage)
        try:
            with connect() as diagnostic_connection:
                client_diagnostics.append_event(diagnostic_connection, organization_id=organization_id,
                    client_id=client_id, event_type=event_type,
                    level='error' if event_type == 'synthesis_failed' else 'info',
                    details={**details, 'revision': revision, 'attempt': int(job['attempt_count'])})
        except Exception:
            # Observability must not fail clinical processing or leak exception bodies.
            LOGGER.warning('Could not persist client diagnostic event (%s).', event_type)

    record('synthesis_claimed', {'stage': 'context'})
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        insights_model = os.getenv("INSIGHTS_MODEL")
        brief_model = os.getenv("PRE_SESSION_MODEL")
        if not api_key or not insights_model or not brief_model:
            raise RuntimeError("synthesis_provider_not_configured")

        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            context = build_clinical_context(connection, organization_id=organization_id, client_id=client_id)
            evidence = context['source_evidence']
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

        record('context_loaded', {'stage': 'context', 'source_count': len(evidence),
                                 'context_bytes': len(json.dumps(context, ensure_ascii=False).encode('utf-8'))})

        bundle = _generate_bundle(
            evidence,
            clinical_context=context,
            insights_model=insights_model,
            brief_model=brief_model,
            on_event=record,
        )
        stage = 'publication'
        source_by_id = {source["evidence_id"]: source for source in evidence}
        evidence_ids = set(source_by_id)
        items = tuple(
            InsightItem(
                item_kind=item["kind"],
                content=item["content"],
                evidence=tuple(
                    InsightEvidence(
                        transcript_segment_id=evidence_id if source_by_id[evidence_id].get('source_type') != 'finalized_clinical_note' else None,
                        clinical_note_version_id=source_by_id[evidence_id].get('clinical_note_version_id'))
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
                generator_version=f"{bundle['snapshot_content']['generator_version']}:{bundle['insights_model']}",
                selection_policy_version=context["policy_version"],
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
        record('synthesis_published', {'stage': 'publication'})
        return True
    except Exception as exc:
        error_code = client_diagnostics.failure_code(exc, stage)
        record('synthesis_failed', {'stage': stage, 'error_code': error_code})
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
