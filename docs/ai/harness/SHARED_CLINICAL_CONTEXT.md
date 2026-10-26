# Shared clinical context and memory

**Status:** Approved product direction; initial shared assembly implemented
**Last updated:** 2026-10-26

## Product outcome

Transcript discovery and longitudinal Insights must reason from the same application-owned client record and saved therapist review state. A new-session review must understand relevant history without restricting discovery to existing prose, themes, or developing trends. Meaningful new topics and evidence that contradicts prior interpretations are first-class results.

Memory lives in versioned application records, not provider conversations. Each call receives a bounded, self-contained projection assembled under one organization/client authorization boundary. Shared assembly and policy apply to initial generation and repair calls. The pre-session brief remains a downstream condensation of validated Insights and its inherited sources; it does not gain independent access to the broader record.

## Authority and information classes

| Class | Meaning and allowed use |
| --- | --- |
| Source evidence | Accepted claims' transcript segments and current therapist-finalized note versions. These are eligible synthesis sources with explicit IDs. Finalized notes represent clinician documentation, not verbatim client speech. |
| Clinician decisions | Saved accepted claim wording/categories and clinician-curated context, with review state. These guide interpretation without becoming independent facts about the client. |
| Pending proposals | Saved, unreviewed claims or curated drafts. These orient attention but are not accepted evidence and cannot be cited as such. Unsaved typing and transient screen selection are excluded. |
| Generated interpretations | Current Insights with their source lineage and review state. These provide comparison context, not independent proof of themselves. |
| Review constraints | Rejected, hidden, stale, and disputed material. These constrain reuse and prevent silent resurrection of rejected interpretations. New direct evidence can still be discovered and reviewed. |

An accepted claim does not make every interpretation attached to its source true. Citation validation establishes source membership and structure, not semantic entailment or clinical correctness. Clinician review remains required.

## Discovery contract

1. Examine the complete new transcript, independently of historical themes.
2. Preserve meaningful novel material, change, contradiction, uncertainty, and unresolved questions, even without a relationship to existing Insights.
3. Use shared context to explain relevance and make direct comparisons, never as an inclusion gate.
4. Ground every new claim in exact segments of the new transcript. Historical notes, claims, and Insights cannot substitute for this evidence.
5. Exclude the same session's existing proposals from the discovery context to avoid anchoring discovery to its baseline output.
6. Keep proposals unreviewed until the therapist decides. Context changes alone do not repeatedly regenerate the same transcript's proposals.

## Synthesis contract

Insights receives the same classes of context as discovery, with a task-specific list of citable sources. Only accepted source-linked transcript evidence and current finalized notes enter that list. Draft notes, superseded note versions, pending proposals, and generated interpretations cannot become accepted source evidence through repetition. A finalized note can support synthesis even when that session has no accepted transcript claim.

Finalized-note citations retain the exact note-version ID through storage, Insights evidence display, and brief projection. The interface identifies them as finalized clinical notes and displays the cited version's content; it does not label them as transcript quotations or offer timestamp playback for them.

## Coordinated Insights and analytical evidence links

The worker makes one stateless Insights request for the entire document, sharing one context packet across trajectories, recurring themes, open threads, and relevant history. This is a coordinated generation, not four independent section calls or provider-held conversational memory. One downstream brief call remains separate. Bounded repair calls retain the whole document and context.

Each section has a distinct purpose: trajectory explains change, theme explains recurrence, open thread preserves an unresolved question, and relevant history supplies necessary background. Prefer fewer substantive items to filling section quotas. A document contains one to eight items with at most two per kind, and unsupported sections may be absent. Place each core observation primarily in one section; source reuse is allowed when it supports a different analytical point. Exact repeated analyses are rejected for whole-document repair. Semantic repetition and analytical usefulness still require model evaluation.

New items supply `analysis_claims`: exact phrases within their analytical prose, each linked to one to four supplied source IDs. One interpretation may therefore cite several accepted transcript passages and finalized notes. The server validates anchors and source membership, maps all IDs back to trusted records, and persists these analytical anchors alongside optional contextual anchors. Empty contextual prose is allowed when it would only repeat the analysis. Saved legacy items remain readable.

The evidence dialog explains that analytical links expose records supporting a generated interpretation for clinician review. They do not mean the phrase was spoken verbatim or the interpretation is established fact. Prose should articulate possible connections, changes, discrepancies, and uncertainty without inventing explanations beyond the evidence.

## Initial implementation bounds and provenance

`database/clinical_context.py` assembles both workers' packets in repeatable-read transactions. It includes at most 120 eligible sources (prioritizing up to 30 current finalized notes), 120 accepted claim decisions, 40 pending proposals, and 30 current interpretations. Review constraints are not silently truncated. Coverage metadata reports omitted records and missing snapshots. Oversized packets fail before provider submission rather than silently cutting clinical text; the packet bound is 250,000 UTF-8 encoded bytes. Initial and repair Insights requests have a separate 350,000-byte bound, including instructions, schema, evidence and repair material. These application safeguards are not the model's token context window; smaller-window providers require their own compatible budget.

Context policy `clinical-context-v2` replaces repeated source bodies in prior interpretations and curated context with `evidence_refs`, retaining source identifiers and session lineage alongside the original interpretation prose and review state. Pending proposals reference eligible sources already present in the packet; unique unreviewed source text remains in the pending proposal and never becomes citable accepted evidence. Synthesis sends eligible source bodies only once in the task evidence list, replacing the nested context source table with `source_evidence_ids`. Request-local aliases are consistent across the evidence list and all context references; persisted citation IDs and the canonical context fingerprint remain unchanged by aliasing. Full finalized-note and accepted transcript text is preserved. This compaction also applies to every whole-document repair.

Each packet carries a policy version and source IDs, note versions, review states, and snapshot identity. Discovery fingerprints the complete transcript/context input. Insights fingerprints the complete context and stores its policy version. Publication preserves existing leases, bounded retries, and therapist decisions. Ordinary logs must not contain clinical prompt content.

These initial limits are operational bounds, not a complete long-term retrieval strategy. Relevance-aware selection, broader history coverage, and retention of context manifests may evolve under this same authority contract.

## Validation

Regression coverage must check review-state separation, finalized-note eligibility and lineage, client scoping, same-session exclusion, fingerprints changing with context, shared context on repairs, and task-specific citation restrictions. Representative governed model evaluations must additionally measure meaningful novel-topic recall, contradictory-evidence preservation, relevance, unsupported interpretation, and repetition bias. Prompt instructions and deterministic citation checks alone do not prove those semantic behaviors.
