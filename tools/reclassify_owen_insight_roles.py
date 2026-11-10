"""Reclassify only existing Owen Insights citations, preserving validated prose."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=False)

from ai_harness.longitudinal_insights import _request_structured_response
from ai_harness.brief_projection import project_accepted_insights
from ai_harness.brief_service import brief_input
from ai_harness.pre_session import generate_openai_pre_session_brief, resolve_brief
from database import synthesis_refresh
from database.connection import connect
from database.longitudinal_records import (
    InsightEvidence,
    InsightItem,
    LongitudinalRecordRepository,
)


ROLES = {"supporting", "contrasting", "context"}


def evidence_id(source: dict[str, object]) -> str:
    return str(source.get("transcript_segment_id") or source.get("clinical_note_version_id"))


def main() -> None:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT client.id AS client_id, client.organization_id, actor.id AS actor_user_id
              FROM app.clients client
              JOIN app.client_portal_accounts portal
                ON portal.client_id=client.id AND portal.status='active'
               AND portal.synthetic_case_key='heartwell-owen'
              JOIN app.client_therapist_access access
                ON access.client_id=client.id AND access.organization_id=client.organization_id
               AND access.revoked_at IS NULL AND access.can_write_clinical
              JOIN app.organization_practitioners practitioner ON practitioner.id=access.practitioner_id
              JOIN app.organization_memberships membership
                ON membership.id=practitioner.membership_id AND membership.status='active'
              JOIN app.application_users actor
                ON actor.id=membership.user_id AND actor.status='active'
             WHERE client.display_name='Owen Park' AND client.status='active'
               AND practitioner.professional_name='Jeremy Heartwell'
        """)
        rows = cursor.fetchall()
        if len(rows) != 1:
            raise RuntimeError("Expected one explicitly synthetic Owen and Jeremy relationship.")
        organization_id = str(rows[0]["organization_id"])
        client_id = str(rows[0]["client_id"])
        actor_user_id = str(rows[0]["actor_user_id"])
        snapshot = LongitudinalRecordRepository(connection).get_latest_insight_snapshot(
            organization_id=organization_id, client_id=client_id,
        )
        appointment = synthesis_refresh.next_appointment(
            connection, organization_id=organization_id, client_id=client_id,
        )
    if not snapshot:
        raise RuntimeError("Owen has no accepted Insights snapshot to reclassify.")
    items_input = []
    allowed_by_item = {}
    for item in snapshot["items"]:
        sources = []
        allowed = set()
        for source in item["evidence"]:
            source_id = evidence_id(source)
            allowed.add(source_id)
            sources.append({
                "evidence_id": source_id,
                "session_id": source["session_id"],
                "session_label": source["session_label"],
                "quote": source.get("quote"),
                "note_text": source.get("note_text"),
            })
        allowed_by_item[item["id"]] = allowed
        items_input.append({
            "item_id": item["id"],
            "kind": item["kind"],
            "content": item["content"],
            "evidence": sources,
        })

    all_item_ids = sorted(allowed_by_item)
    all_evidence_ids = sorted(set().union(*allowed_by_item.values()))
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "minItems": len(all_item_ids),
                "maxItems": len(all_item_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["item_id", "evidence_roles"],
                    "properties": {
                        "item_id": {"type": "string", "enum": all_item_ids},
                        "evidence_roles": {
                            "type": "array", "minItems": 1, "maxItems": 28,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["evidence_id", "role"],
                                "properties": {
                                    "evidence_id": {"type": "string", "enum": all_evidence_ids},
                                    "role": {"type": "string", "enum": sorted(ROLES)},
                                },
                            },
                        },
                    },
                },
            },
        },
    }
    payload = {
        "model": os.environ["INSIGHTS_MODEL"],
        "store": False,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 8_000,
        "instructions": (
            "Classify each existing citation relative to the direction of its insight item. "
            "Do not rewrite, summarize, diagnose, or add/remove evidence. Supporting means the session observation "
            "aligns with the item's directional theme or trajectory. Contrasting means it moves against, weakens, "
            "complicates, or contradicts that direction, even when it supports the broader statement that change "
            "was mixed. Context only orients the reader without directional support. In a help-seeking trajectory, "
            "contacting support is supporting while drinking later that evening is contrasting; both in one session "
            "create mixed activity. Do not manufacture contrast or satisfy a quota. Return every item and every "
            "evidence ID exactly once."
        ),
        "input": json.dumps({"task": "directional_evidence_role_classification", "items": items_input}, ensure_ascii=False),
        "text": {"format": {"type": "json_schema", "name": "directional_evidence_roles", "strict": True, "schema": schema}},
    }
    generated, response = _request_structured_response(payload, os.environ["OPENAI_API_KEY"])
    generated_by_item = {}
    for result in generated["items"]:
        item_id = result["item_id"]
        if item_id in generated_by_item:
            raise RuntimeError("Role classifier duplicated an Insights item.")
        roles = {}
        for link in result["evidence_roles"]:
            source_id = link["evidence_id"]
            role = link["role"]
            if source_id in roles or source_id not in allowed_by_item[item_id] or role not in ROLES:
                raise RuntimeError("Role classifier returned invalid evidence coverage.")
            roles[source_id] = role
        if set(roles) != allowed_by_item[item_id]:
            raise RuntimeError("Role classifier did not cover each existing citation exactly once.")
        generated_by_item[item_id] = roles
    if set(generated_by_item) != set(all_item_ids):
        raise RuntimeError("Role classifier did not cover each Insights item exactly once.")

    materialized = []
    packet_items = []
    role_counts = {role: 0 for role in sorted(ROLES)}
    for index, item in enumerate(snapshot["items"]):
        roles = generated_by_item[item["id"]]
        evidence = []
        for source in item["evidence"]:
            role = roles[evidence_id(source)]
            role_counts[role] += 1
            evidence.append(InsightEvidence(
                transcript_segment_id=source.get("transcript_segment_id"),
                clinical_note_version_id=source.get("clinical_note_version_id"),
                evidence_role=role,
            ))
        materialized.append(InsightItem(
            item_kind=item["kind"],
            content=item["content"],
            evidence=tuple(evidence),
            review_state=item["review_state"],
            display_order=item["display_order"],
        ))
        packet_items.append({
            "kind": item["kind"],
            "content": item["content"],
            "evidence": [
                {**source, "evidence_role": roles[evidence_id(source)]}
                for source in item["evidence"]
            ],
        })

    packet = {
        "snapshot_id": "pending-publication",
        "snapshot_version": int(snapshot["version"]) + 1,
        "items": packet_items,
    }
    brief = brief_metadata = None
    if appointment:
        projected = project_accepted_insights(packet, [])
        _, brief_request = brief_input(projected)
        brief_response, brief_metadata = generate_openai_pre_session_brief(
            synthesis_request=brief_request,
            api_key=os.environ["OPENAI_API_KEY"],
            model=os.environ["PRE_SESSION_MODEL"],
        )
        brief = resolve_brief(brief_response, brief_request["evidence"])

    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT desired_insights_revision, published_insights_revision, status, last_error_code
              FROM app.clinical_synthesis_refresh_state
             WHERE organization_id=%s AND client_id=%s
             FOR UPDATE
        """, (organization_id, client_id))
        state = cursor.fetchone()
        if not state or int(state["desired_insights_revision"]) == int(state["published_insights_revision"]):
            revision = synthesis_refresh.enqueue_insights_refresh(
                connection,
                organization_id=organization_id,
                client_id=client_id,
                event_type="reprocess_requested",
                actor_user_id=actor_user_id,
                target_type="longitudinal_insight_snapshot",
                target_id=snapshot["id"],
                debounce_seconds=0,
            )
        else:
            revision = int(state["desired_insights_revision"])
            cursor.execute("""
                UPDATE app.clinical_synthesis_refresh_state
                   SET status='pending', attempt_count=0, not_before=CURRENT_TIMESTAMP,
                       processing_insights_revision=NULL, worker_token=NULL,
                       lease_expires_at=NULL, updated_at=CURRENT_TIMESTAMP
                 WHERE organization_id=%s AND client_id=%s
                   AND status IN ('pending', 'failed')
                   AND last_error_code='context_too_large'
            """, (organization_id, client_id))
            if cursor.rowcount != 1:
                raise RuntimeError("Owen's existing role revision cannot be safely reclaimed.")
        worker_token = str(uuid4())
        job = synthesis_refresh.claim_due_insights_refresh(
            connection, worker_token=worker_token, lease_seconds=1800,
            organization_id=organization_id, client_id=client_id,
        )
    if not job or int(job["processing_insights_revision"]) != revision:
        raise RuntimeError("Could not claim Owen's role-reclassification revision.")

    with connect() as connection:
        repository = LongitudinalRecordRepository(connection)
        latest = repository.get_latest_insight_snapshot(
            organization_id=organization_id, client_id=client_id,
        )
        if not latest or latest["id"] != snapshot["id"]:
            raise RuntimeError("Owen's source Insights snapshot changed before role publication.")
        snapshot_id = repository.create_insight_snapshot(
            organization_id=organization_id,
            client_id=client_id,
            content=snapshot["content"],
            items=tuple(materialized),
            generator_name="Directional evidence role classifier",
            generator_version=f"directional-role-v1:{response.get('model', os.environ['INSIGHTS_MODEL'])}",
            selection_policy_version=snapshot["selection_policy_version"],
            actor_user_id=actor_user_id,
            status="accepted",
            parent_snapshot_id=snapshot["id"],
        )
        appointment_id = str(appointment["id"]) if appointment else None
        brief_id = repository.create_pre_session_brief_snapshot(
            organization_id=organization_id,
            client_id=client_id,
            context_packet={**packet, "snapshot_id": snapshot_id},
            content=brief,
            generator_name="Queued pre-session editorial synthesis",
            generator_version=(brief_metadata or {}).get("model", os.environ["PRE_SESSION_MODEL"]),
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

    print(json.dumps({
        "published_revision": revision,
        "snapshot_id": snapshot_id,
        "role_counts": role_counts,
        "usage": response.get("usage") or {},
        "brief_usage": (brief_metadata or {}).get("usage") or {},
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
