"""Bounded clinician guidance, kept separate from verbatim source evidence."""

from typing import Any


def with_clinician_guidance(packet: dict[str, Any] | None, entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    guidance = []
    for entry in entries:
        if entry.get('status') != 'accepted' or not entry.get('text', '').strip():
            continue
        evidence = [source for source in entry.get('evidence', [])
                    if source.get('evidence_id') and source.get('session_id') == entry.get('session_id')
                    and source.get('quote', '').strip()]
        if not evidence:
            continue
        guidance.append({
            'entry_id': entry['id'], 'category': entry['category'],
            'clinician_interpretation': entry['text'], 'evidence': evidence,
        })
        if len(guidance) == 8:
            break
    if packet is None and not guidance:
        return None
    return {**(packet or {'items': []}), 'clinician_guidance': guidance}
