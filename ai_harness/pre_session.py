"""Provider-neutral request building and citation validation for pre-session briefs."""
from collections.abc import Iterable
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BRIEF_SECTIONS = (
    "Since last session",
    "Active focus",
    "Important trajectory",
    "Open loops",
    "Relevant history",
)


def build_pre_session_synthesis_request(*, client_reference: str, evidence: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build the complete, bounded model request from approved evidence only.

    The returned value is provider-neutral. A future provider adapter may convert
    it to an API-specific request, but must not add client history outside this
    evidence list or weaken the output contract.
    """
    selected_evidence = list(evidence)
    return {
        "task": "Draft a concise pre-session brief for clinician review.",
        "client_reference": client_reference,
        "instructions": [
            "Use only the supplied evidence.",
            "Write no more than one concise item per supplied evidence item.",
            "Frame patterns as possible prompts for clinician review, not facts.",
            "Do not diagnose, determine risk, recommend treatment, or make a clinical decision.",
            "Attach one or more supplied evidence_id values to every item.",
            "Return only the defined structured response.",
        ],
        "response_contract": {
            "sections": list(BRIEF_SECTIONS),
            "item_fields": ["text", "evidence_ids"],
            "maximum_items_per_section": 3,
        },
        "evidence": selected_evidence,
    }


def validate_pre_session_response(response: dict[str, Any], evidence: Iterable[dict[str, Any]]) -> list[str]:
    """Return contract violations; an empty list means referentially valid.

    This validates output shape and citation membership only. It deliberately
    does not claim to validate clinical correctness or safety.
    """
    errors: list[str] = []
    permitted_ids = {item.get("evidence_id") for item in evidence}
    sections = response.get("sections")
    if not isinstance(sections, list):
        return ["Response must contain a sections list."]
    for section in sections:
        if not isinstance(section, dict) or section.get("title") not in BRIEF_SECTIONS:
            errors.append("Response contains an unsupported section.")
            continue
        items = section.get("items")
        if not isinstance(items, list) or len(items) > 3:
            errors.append(f"{section.get('title', 'Section')} must contain no more than three items.")
            continue
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                errors.append("Every brief item must include text.")
                continue
            citations = item.get("evidence_ids")
            if not isinstance(citations, list) or not citations:
                errors.append("Every brief item must cite evidence.")
            elif any(citation not in permitted_ids for citation in citations):
                errors.append("A brief item cites evidence outside the supplied bundle.")
    return errors


def pre_session_response_schema() -> dict[str, Any]:
    """Return the strict structured-output contract for a model provider."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["sections"],
        "properties": {
            "sections": {
                "type": "array",
                "minItems": 1,
                "maxItems": len(BRIEF_SECTIONS),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["title", "items"],
                    "properties": {
                        "title": {"type": "string", "enum": list(BRIEF_SECTIONS)},
                        "items": {
                            "type": "array",
                            "maxItems": 3,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["text", "evidence_ids"],
                                "properties": {
                                    "text": {"type": "string", "maxLength": 420},
                                    "evidence_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                                },
                            },
                        },
                    },
                },
            },
        },
    }


def generate_openai_pre_session_brief(*, synthesis_request: dict[str, Any], api_key: str, model: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate and validate one synthetic pre-session draft through OpenAI.

    This provider adapter deliberately uses a stateless response and does not
    attach web search, file search, conversation state, or identifying metadata.
    Callers are responsible for restricting it to approved data.
    """
    payload = {
        "model": model,
        "store": False,
        # Reasoning-capable models may use part of this budget before emitting
        # the structured draft. Keep the limit small, but leave room for it.
        "max_output_tokens": 2_000,
        "instructions": "\n".join(synthesis_request["instructions"]),
        "input": json.dumps({
            "task": synthesis_request["task"],
            "client_reference": synthesis_request["client_reference"],
            "evidence": synthesis_request["evidence"],
        }),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "pre_session_brief",
                "strict": True,
                "schema": pre_session_response_schema(),
            },
        },
    }
    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI request failed ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise RuntimeError("Could not reach OpenAI.") from exc

    output_text = response_data.get("output_text")
    if not output_text:
        output_text = next((content["text"] for item in response_data.get("output", []) for content in item.get("content", []) if content.get("type") == "output_text"), "")
    if not output_text:
        output_shape = [
            {
                "type": item.get("type"),
                "content_types": [content.get("type") for content in item.get("content", [])],
            }
            for item in response_data.get("output", [])
        ]
        raise RuntimeError(
            "OpenAI returned no structured output "
            f"(status={response_data.get('status')}, output={output_shape})."
        )
    try:
        generated = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI returned invalid structured output.") from exc

    violations = validate_pre_session_response(generated, synthesis_request["evidence"])
    if violations:
        raise RuntimeError("OpenAI output did not satisfy the evidence contract: " + "; ".join(violations))
    return generated, {"model": response_data.get("model", model), "response_id": response_data.get("id"), "usage": response_data.get("usage", {})}
