# Granular pre-session citations

The model emits ordered text parts: plain connecting text has no citations, while
short claim parts carry their own evidence IDs and scope. The server concatenates
these parts and computes phrase locations deterministically. This avoids asking
the model to count character positions or reproduce a phrase in a second field.
The persisted and rendered representation contains plain item text plus claims. Each claim contains an exact phrase
in that generated text, its zero-based occurrence, evidence_ids, and scope
(single_exchange or cross_session). The phrase may paraphrase the source. No
keywords or lexical matching decide which words become bold.

The server rejects missing, overlapping or word-splitting spans, invented IDs,
and cross-session claims without at least two distinct source sessions. This
checks referential integrity, not semantic entailment or clinical correctness.
The UI resolves each phrase to only its own trusted source records; quotations,
recording offsets and session labels come from the database, never the model.

## Generation and persistence

POST /clinical-records/clients/{client_id}/pre-session-brief/generate?organization_id=...
requires authenticated clinical write access. It uses the accepted context that
feeds the existing brief, calls the configured provider and validates the output.
It rechecks authorization and context before saving. GET serves this generated
brief only when its context fingerprint still matches; otherwise it returns
current accepted context with sentence-level evidence links. Reading never
calls the model. No manual refresh button has been added.

Apply database/migrations/017_generated_pre_session_briefs.sql through
`python -m tools.apply_session_review_migration`. Existing brief reads continue
working before migration. Configure OPENAI_API_KEY, PRE_SESSION_MODEL and the
comma-separated PRE_SESSION_MODEL_APPROVED_CLIENT_IDS in the server environment.
Client allowlisting is deployment configuration, not a substitute for approved
provider/data handling terms. Do not enable real-client processing without that
approval. Generation is explicit through the authenticated endpoint; automatic
background generation is not yet scheduled.

The stored response includes the original IDs, model, generating actor, time and
context hash. Source edits or accepted-context changes invalidate it on read.
Legacy records have no guessed phrase citations. A fresh generation is necessary
to populate model-selected highlights.

Validation: tests/test_pre_session_claims.py covers paraphrased claims, per-claim
source resolution, unknown IDs, invalid occurrences, overlaps, longitudinal
support and context invalidation. tests/test_brief_projection.py covers fallback
and access checks. The schema does not establish that a cited exchange actually
supports the model claim; clinician review remains necessary.
