# Clinical synthesis generation lifecycle

> Product and architecture decision for draft clinical notes, the Insights workspace, and pre-session briefs.

**Status:** Approved direction  
**Last updated:** 2026-10-05

**Implementation status:** The durable queue, leased model worker, atomic Insights/next-brief publication, freshness UI, and API-lifecycle worker dispatch are checked in. Finalized notes and evidence-review decisions enqueue Insights revisions; the worker keeps the last valid pair readable until its replacement validates and commits. A daily reconciliation scheduler remains to be configured in hosted infrastructure.

## 1. Authority and derived views

The canonical clinical record is the source of truth. Generated artifacts are versioned, reviewable views over that record.

```text
Corrected transcript and AI draft clinical note
        -> therapist-finalized clinical-note version
        -> current validated Insights snapshot
        -> read-only pre-session brief for an upcoming appointment
```

- The AI-produced clinical note is always labeled as a draft until a therapist explicitly finalizes it.
- Finalizing a note records the author, source transcript version, finalizer, and time. Later corrections create a new version rather than silently changing the finalized record.
- Insights is the main client-level clinical synthesis environment. It owns longitudinal interpretation, evidence-linked themes, trajectories, open threads, and clinician-curated context.
- The pre-session brief is a concise orientation view. It is not an independently editable record or a second longitudinal reasoning system.

Therapist-finalized records outrank generated material. Generated patterns remain review prompts, not diagnoses, risk determinations, or treatment decisions.

## 2. Insights refresh events

Every durable change that can alter the current Insights environment appends an auditable, client-scoped refresh event. Qualifying events include:

- finalizing or amending a clinical-note version;
- finalizing or correcting a transcript or speaker attribution used as evidence;
- accepting, editing, dismissing, hiding, disputing, pinning, or marking an evidence claim or insight outdated;
- adding or changing clinician-curated longitudinal context;
- changing evidence links or the source status of material represented in Insights; and
- an administrative reprocessing request after a model, prompt, retrieval-policy, or verifier version change.

Transient UI activity does not enqueue refresh work. Keystrokes in an unfinalized draft, navigation, opening evidence, and viewing Insights are not generation triggers. Saving an ordinary draft may be versioned for recovery, but it does not become eligible source material until the therapist finalizes it.

## 3. Queue and refresh policy

Insights refresh is background-first and event-driven.

1. A qualifying transaction writes the clinical change and its refresh event atomically.
2. The client receives a monotonically increasing desired Insights revision.
3. Closely timed events are coalesced during a short debounce window so several review actions can produce one generation.
4. High-value clinician actions, including note finalization and accepting or dismissing an evidence claim, request prompt processing rather than waiting for an event-count threshold.
5. A queue-size threshold may accelerate processing, while a maximum queue-age threshold guarantees that low-volume changes do not wait indefinitely. Neither threshold replaces prompt processing for high-value clinician actions.
6. A rolling daily reconciliation finds missed, delayed, failed, or revision-mismatched work. It does not blindly regenerate unchanged clients and is a safety net rather than the normal refresh mechanism.
7. Work is idempotent by organization, client, desired revision, and input fingerprint. Concurrent events are not lost: if the desired revision advances during generation, another refresh remains queued.
8. A newly generated snapshot becomes current only after its structure, source membership, phrase anchors, and policy constraints validate. Until then, the last valid snapshot remains visible.
9. Failures use bounded retries and then surface a non-clinical operational status without replacing the last valid snapshot.

This policy should be tuned with observed generation latency, event frequency, cost, and therapist freshness expectations. Initial thresholds are operational configuration, not permanent product semantics.

## 4. Insights interface behavior

The interface should not ask therapists to perform routine system maintenance.

The page's presentation and progressive-disclosure contract is defined in
[Insights progressive disclosure architecture](../design/INSIGHTS_PROGRESSIVE_DISCLOSURE.md).
Insights uses a stable semantic hierarchy, hides unsupported modules, and places
clinically useful current material above background context, orientation counts,
and the accepted evidence record.

- While work is queued or running, keep the last valid snapshot readable and show a quiet status such as **Updating insights**.
- Do not expose a manual Insights regeneration control. Crossing a threshold should make the background worker run without transferring maintenance responsibility to the therapist.
- Avoid an interruptive popup that says the therapist must refresh. Delayed or failed work may surface a quiet operational status and recover through the background retry and reconciliation paths.
- Display the snapshot's source-through time or equivalent freshness information when useful.
- Review actions should acknowledge immediately that the change was saved and Insights will update in the background.

Accepting and dismissing an evidence claim are both first-class changes. Dismissal must remove or constrain the rejected material in subsequent snapshots rather than merely hiding it in the current browser.

## 5. Insights generation boundary

An Insights refresh reads only eligible, client-scoped, versioned sources under the clinical authorization boundary. It may use:

- therapist-finalized notes and corrected transcripts;
- therapist-curated items and review-state decisions;
- previously validated Insights material when the input versions and lifecycle states remain current; and
- explicitly labeled source-linked proposals where the product permits an unreviewed state.

It must exclude or appropriately constrain hidden, stale, disputed, rejected, superseded, or unfinalized material. Every contextual evidence statement requires explicit source identifiers. The interface never guesses phrase anchors from lexical similarity.

Configuring the OpenAI API key plus the Insights and pre-session model names opts the deployment into background synthesis for every eligible client. Eligibility comes from the source lifecycle and authorization boundary, not a manually maintained client allowlist. The worker may be paused deployment-wide for incident response or policy review.

Incremental generation may update affected portions for responsiveness. A periodic full reconciliation from eligible canonical records should detect drift and confirm that the current snapshot still reflects all lifecycle controls.

### Transcript proposal analysis

New-session evidence proposals may use the current validated Insights snapshot as
versioned comparison context when suggesting categories and a concise
future-synthesis focus. The proposal must remain anchored to direct transcript
evidence; prior Insights cannot become evidence for the new claim. Persist the
source Insights snapshot ID and generator version with each proposal. Reviewing a
proposal may advance Insights, but that new snapshot does not regenerate the same
session's pending proposals unless their source transcript version changes. This
keeps review stable and prevents a same-session model feedback loop.

For each completed upload, the application creates one durable proposal-analysis
job keyed to the exact transcript version. The job reads the complete normalized
transcript in a single bounded pass, discovers a selective set of claims, assigns
all directly useful review categories, and writes a concise future-synthesis focus
for each claim. Every claim must cite one or more exact transcript segment IDs.
The pass may compare against the current validated Insights snapshot, but Insights
never substitutes for transcript evidence.

Transcript persistence and the HealthScribe clinical-note draft do not wait for
this secondary pass. Until it succeeds, source-linked HealthScribe proposals may
remain available as a baseline. Successful publication atomically replaces only
unreviewed baseline proposals; accepted or dismissed therapist decisions are never
overwritten. Jobs are idempotent per transcript version, use bounded retries and a
recoverable worker lease, and retain model, prompt-version, input-fingerprint,
usage, response, failure, and source-snapshot provenance without logging clinical
prompt content. Configuring both the OpenAI API key and proposal model opts that
deployment into the pass for every completed transcript upload, regardless of
account type. This keeps proof-of-concept uploads predictable and avoids
per-client eligibility state. A production deployment must not configure that
provider path for real clinical data until its external-model data flow, consent,
contractual, retention, privacy, security, and clinical-policy controls are approved.

## 6. Pre-session brief contract

Pre-session brief generation is background-only. Opening or reading a scheduled session never calls a model, and the therapist does not edit or manually regenerate the brief.

The brief generator receives only the current validated Insights snapshot and its trusted source mappings, plus appointment metadata needed to identify the upcoming session. It does not retrieve independently from transcripts, clinical notes, or the broader client record.

The brief generator is an editorial selector and compressor. It may:

- choose a small number of current Insight items relevant to the next conversation;
- write a concise natural-language orientation and a few open loops; and
- choose short, exact phrases in that prose as links to the specific inherited evidence claims.

It may not introduce a new clinical interpretation, trend, diagnosis, risk assessment, or treatment recommendation. Reliability evaluation and future clinical fine-tuning should concentrate on Insights; the brief is evaluated for faithful selection, compression, freshness, and citation preservation.

The pre-session brief is a downstream materialized view of Insights, presented in the scheduled-session workflow. Publishing a new current Insights snapshot automatically invalidates any brief based on an older snapshot and requests its background replacement when an upcoming appointment exists.

Brief generation is requested when:

- a new validated Insights snapshot becomes current and the client has an upcoming appointment;
- an appointment is scheduled for a client with a current Insights snapshot; or
- a scheduled freshness check finds that the next appointment lacks a brief for the current Insights revision.

Each brief is tied to the appointment and exact Insights snapshot version that informed it. If a replacement fails validation, the last valid brief may remain visible with an honest freshness state. The read path never triggers generation and never invents phrase anchors. Legacy or fallback content uses explicit statement-level evidence links.

## 7. State and audit requirements

At minimum, retain:

- the refresh-event type, actor or system origin, affected record version, and creation time;
- desired, processing, and published Insights revisions per client;
- input fingerprint, model and prompt configuration, verifier result, and generation time;
- the exact eligible source versions and review-state decisions used by a snapshot;
- the appointment and Insights snapshot version used by each brief; and
- retry, failure, supersession, and publication events without sensitive prompt content in ordinary logs.

The queue is operational state, not the clinical record. Consuming a queue event never deletes the underlying audit history or source versions.

## 8. Initial implementation sequence

1. Complete explicit clinical-note finalization and amendment versioning.
2. Add the client-scoped synthesis refresh event ledger and revision watermark.
3. Run validated Insights refreshes from eligible finalized sources and review controls.
4. Add debounce, idempotency, bounded retries, and daily reconciliation.
5. Expose quiet freshness and failure states without a manual regeneration control.
6. Trigger appointment-scoped pre-session brief generation exclusively from published Insights snapshots.
7. Evaluate grounding, rejected-item removal, stale-source behavior, freshness, and harmful-overreach regressions before production use.
