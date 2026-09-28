"""Versioned context identity and model request assembly for persisted briefs."""
import hashlib
import json
from ai_harness.pre_session import build_pre_session_synthesis_request


def brief_input(brief):
    evidence = {}
    context = []
    for section in brief['sections']:
        for item in section['items']:
            context.append({'text': item['text'], 'evidence_ids': [s['evidence_id'] for s in item['sources']]})
            for source in item['sources']:
                evidence[source['evidence_id']] = source
    sources = sorted(evidence.values(), key=lambda source: source['evidence_id'])
    fingerprint = hashlib.sha256(json.dumps({'version': 2, 'context': context, 'evidence': sources}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    request = build_pre_session_synthesis_request(client_reference='current-client', evidence=sources, context_packet={'accepted_context': context})
    return fingerprint, request
