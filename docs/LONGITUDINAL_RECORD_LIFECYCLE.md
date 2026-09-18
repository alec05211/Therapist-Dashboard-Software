# Longitudinal record lifecycle

## Purpose

The Insights workspace is the application-owned, reviewable longitudinal record for one therapist-client relationship. It is not a model memory and does not make diagnoses, determine risk, or make treatment decisions.

## Record flow

```text
Completed session
  → reviewed/finalized transcript version and timestamped segments
  → therapist-finalized clinical-note revision
  → longitudinal insight snapshot with evidence links
  → therapist review, edits, acceptance, hiding, staleness, or dispute
  → bounded pre-session context packet
  → saved pre-session brief draft
```

Each arrow records a new version; prior source material remains inspectable.

## Source precedence

1. Therapist-finalized transcript corrections and clinical-note revisions.
2. Therapist-curated longitudinal items.
3. Reviewed generated synthesis.
4. Provider-generated draft artifacts.

Provider-generated clinical notes are never implicitly treated as therapist-authored or final.

## What an insight snapshot may contain

- Source-grounded possible trajectories or themes, supported by one or more transcript segments.
- Explicitly unresolved threads and clinician-curated context.
- Relevant historical context that has been deliberately retained.
- Item review state: draft, accepted, hidden, stale, or disputed.

It must not contain autonomous diagnoses, risk determinations, or treatment decisions.

## Context packet selection

The pre-session brief receives a bounded packet rather than the entire client history. The initial selection policy includes:

1. The latest finalized session’s relevant record.
2. A small number of accepted, multi-session review prompts.
3. Explicit open threads and clinician-pinned context.
4. Source citations for every selected item.

Items marked hidden, stale, or disputed are excluded by default. The packet itself is saved with the resulting brief so a therapist can later see exactly what informed it.

## Database implementation

Migration `002_longitudinal_insight_records.sql` adds:

- `clinical_note_versions`
- `longitudinal_insight_snapshots`
- `longitudinal_insight_items`
- `longitudinal_insight_evidence`
- `pre_session_brief_snapshots`

The migration has not been applied to the private RDS instance. Apply it only through the documented private Fargate migration workflow after review.
