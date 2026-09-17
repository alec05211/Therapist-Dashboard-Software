# Clinical AI Orchestration and Evidence Harness

> A working architecture for clinician-facing longitudinal memory and synthesis. This document is a proposed design, not a claim of HIPAA compliance, clinical validation, or approval to process real clinical data with any particular model provider.

**Status:** Proposed architecture — no production implementation yet  
**Related:** [Project vision](PROJECT_VISION.md), [AI / ML vision](AI_ML_VISION.md), [storage architecture](storage-architecture/STORAGE_ARCHITECTURE.md), [current HealthScribe implementation](HEALTHSCRIBE.md)

## 1. What “harness” means here

A **harness** is the application-controlled layer around a model. It turns a raw model API into a bounded product capability by deciding:

1. who is allowed to request an output;
2. which client record and source versions may be used;
3. what narrowly selected evidence is sent to a model;
4. which task and safety constraints apply;
5. how citations and structured output are checked;
6. what is shown to the therapist, stored, and auditable; and
7. how therapist corrections change future retrieval.

This is sometimes called an **AI orchestration layer**, **LLM gateway**, or **evidence harness**. “Harness” is appropriate internally, but it is not a formal clinical or regulatory term. In this product, **clinical AI orchestration and evidence harness** is the clearest name.

The harness is not a model, does not retain a hidden client memory, and does not replace the clinical record. It uses an application-owned record to construct a bounded request for each generation.

## 2. Core model: one canonical record, two derived views

Do not maintain a separate opaque “snapshot” as the client’s truth. The canonical, versioned clinical record remains the source of truth. The system derives two distinct views from it:

| View | Purpose | Lifetime |
| --- | --- | --- |
| **Longitudinal memory projection** | Small, editable, evidence-linked items useful for retrieval: finalized summaries, goals, open loops, clinician-curated facts, and themes. | Continuously maintained; records are versioned and can be superseded or removed. |
| **Pre-session brief snapshot** | The exact concise brief and evidence bundle shown before one session. | Immutable historical artifact after creation; later corrections create a new brief rather than silently rewriting history. |

The broader **clinical journey review** is not a third datastore. It is an evidence-rich interface over the canonical record and the longitudinal memory projection.

## 3. Architecture boundary

```text
Authorized therapist UI
        |
        v
Application API and clinical authorization
        |
        +--> Canonical clinical record
        |       RDS PostgreSQL: versions, permissions, metadata, audit events
        |       Private S3: audio and large/raw artifacts
        |
        +--> Clinical AI orchestration and evidence harness
                1. policy gate
                2. retrieval and context builder
                3. model gateway
                4. output/citation verifier
                5. draft and audit writer
                         |
                         v
                Approved external frontier-model account
                or future self-hosted / private model provider
```

The external model provider is a replaceable processing dependency. It is never the authority for clinical access, storage, longitudinal memory, source-of-truth content, or therapist corrections.

## 4. Components and responsibilities

### A. Canonical clinical record

The storage architecture already defines the base boundary: PostgreSQL stores protected relational/version metadata and S3 stores protected large artifacts. The record includes raw HealthScribe output, normalized application output, therapist corrections, finalized transcript versions, and reviewed note versions.

The harness reads a versioned record; it never overwrites it.

### B. Longitudinal memory projection

This is an application-owned, per-client set of compact records derived from finalized sessions or directly created by a clinician. It is not an embedding database alone.

Each item should include:

- organization and client identifiers;
- item type, such as `finalized_session_summary`, `active_goal`, `open_loop`, `clinician_pinned_context`, `possible_pattern`, or `relevant_history`;
- content and status (`active`, `superseded`, `hidden`, `outdated`, or `deleted` according to approved retention policy);
- author/provenance: therapist, model draft accepted by therapist, or import;
- source session/note/transcript references and optional timestamp ranges;
- importance, recency, and review date where meaningful;
- version, creation time, editor, and audit references.

Semantic embeddings may later assist retrieval, but structured filters and clinician curation must work without them.

### C. Policy gate

Before any retrieval or generation, the application verifies the requesting therapist’s explicit client relationship, organization boundary, permitted operation, consent state, and applicable retention or legal-hold conditions. A model call is denied if this gate fails.

### D. Retrieval and context builder

This component builds a minimal evidence bundle for one defined task. For a pre-session brief it may select:

- the most recent therapist-finalized session summary and plan;
- active, clinician-approved goals and pinned context;
- unresolved follow-ups and planned actions;
- a small number of relevant historical items;
- source references needed to substantiate every statement.

It should rank by task relevance, recency, clinician importance, and unresolved status—not merely semantic similarity. It must use the correct therapist-client relationship and never retrieve across clients or organizations.

### E. Model gateway

The server, not the browser, holds a single approved provider credential for the application or environment. It may make many independently authorized requests for many clients, while the application maintains client separation.

Each request includes only the task-specific evidence bundle and rules. The provider does not receive the full database, has no implicit access to previous requests, and must not be treated as the client’s memory. Provider selection and configuration require separate privacy, legal, security, retention, and data-use approval before real clinical data is sent.

### F. Output and citation verifier

The model returns structured output, not free-form application state. The harness validates:

- the expected brief sections and length limits;
- that every factual item has one or more valid source identifiers;
- that citations resolve to a source in the request bundle;
- that unsupported or disallowed clinical claims are rejected or flagged;
- that the result is marked as a clinician-reviewed draft.

Validation proves referential grounding, not clinical correctness. The therapist remains the reviewer.

### G. Generated-artifact and audit writer

For each generation, save a versioned brief record with the task, source versions, selected memory-item identifiers, provider/model configuration identifier, creation time, review state, and therapist edits. Avoid placing sensitive prompts or outputs in ordinary provider, application, or observability logs; store any required protected request record under the approved clinical-data controls.

## 5. Primary workflows

### Pre-session brief

1. A therapist opens an upcoming session.
2. The API authorizes access to that client and checks whether a recent suitable brief exists.
3. The context builder selects a compact evidence bundle from finalized and clinician-curated records.
4. The model gateway requests a concise, source-cited draft under explicit no-diagnosis/no-risk/no-treatment-decision rules.
5. The verifier checks structure and citations.
6. The UI shows a five-minute brief with links to its supporting finalized note, transcript excerpt, and synchronized audio when available.
7. Therapist edits, pins, dismisses, or marks items outdated; those choices update the memory projection and are auditable.

### Clinical journey review

1. An authorized therapist opens the client’s history.
2. The application shows a timeline of finalized sessions and their evidence-linked memory items.
3. The therapist examines sources, corrects labels/content, hides stale material, and pins useful context.
4. The next brief uses those updated decisions rather than silently preserving an obsolete model output.

## 6. Concise pre-session brief contract

The initial brief should be constrained to a small set of sections:

- **Since last session:** changed items and the previous session’s final plan.
- **Active focus:** current clinician-approved goals or themes.
- **Important trajectory:** a cautiously phrased, source-backed change across sessions.
- **Open loops:** unfinished follow-up, planned discussion, or client-stated commitment.
- **Relevant history:** only older material materially related to the upcoming session.

Each item displays its session date and supports “view evidence.” Possible patterns are prompts for therapist review, not findings. The brief excludes diagnosis, risk determination, treatment recommendations, speculative emotional certainty, and a comprehensive personal dossier.

## 7. Initial data-model extensions

The existing `transcript_version`, `synthesis_version`, and `audit_event` design is the base. Proposed additions are:

| Record | Responsibility |
| --- | --- |
| `longitudinal_memory_item` | Editable, evidence-linked per-client retrieval unit and lifecycle state. |
| `memory_item_source` | Join from a memory item to one or more session/note/transcript sources and timestamp ranges. |
| `pre_session_brief` | Versioned generated or clinician-authored orientation artifact for an upcoming session. |
| `brief_evidence_item` | Immutable record of the exact source/memory versions selected for one brief. |
| `ai_generation` | Provider/model configuration, bounded task type, request/protected-output references, validation outcome, and review state. |

These records inherit the organization and clinical-access rules in the storage architecture. They do not introduce a general shared vector store across clients.

## 8. Delivery sequence for a solo project

1. Finish transcript and note finalization/versioning.
2. Add manually curated memory items and evidence links without any model call.
3. Build the clinical journey review timeline and correction controls.
4. Implement deterministic pre-session retrieval using recency, open-loop, and clinician-pinned rules.
5. Add frontier-model synthesis behind the gateway and structured-output verifier using synthetic or otherwise approved data.
6. Evaluate brief usefulness, grounding, and correction behavior before broader insight generation.
7. Add embeddings or fine-tuning only when evaluation identifies a specific failure that simple retrieval and prompting cannot solve.

## 9. Open decisions before production

- The approved external model provider, account configuration, and contractual/privacy/security conditions for real clinical data.
- Exact consent wording and whether a client may opt out of specific AI processing while retaining recording/transcription.
- Retention/deletion treatment for memory items, generated briefs, provider request records, indexes, and backups.
- The task-specific retrieval policy and maximum evidence size for a five-minute brief.
- Review requirements and escalation behavior if potentially urgent source content is surfaced; the system must not make or represent a risk determination.
- Measurement thresholds for citation validity, therapist usefulness, stale-memory errors, and harmful overreach.
