# Insights progressive disclosure architecture

> Product and presentation contract for progressively revealing therapist-facing clinical synthesis.

**Status:** Approved direction  
**Last updated:** 2026-10-27

## 1. Purpose

Insights is an evidence-driven clinical document, not a fixed dashboard whose
sections unlock after a prescribed number of sessions. It should expose the most
useful supported information first, make deeper context easy to inspect, and
omit material that the eligible record does not support.

The upper viewport is the therapist's current working picture. Scrolling
progressively reveals interpretation, recurrence, background context, and the
accepted evidence record. The interface must not fill empty categories merely
to make the page appear complete.

## 2. Page hierarchy

Modules use this stable semantic order:

1. **Clinical overview** - a concise source-grounded synthesis of the current
   record. With one session it is session-scoped; it becomes longitudinal as the
   evidence grows.
2. **At-a-glance metrics** - compact record-navigation counts, including current
   themes, open threads, accepted evidence, and the accepted-evidence delta from
   the latest represented session. Theme recurrence remains in the same panel.
   These counts are never clinical scores.
3. **Current focus** - open threads, current priorities, recent commitments, and
   other supported material likely to matter in the next session.
4. **Changes over time** - evidence-linked change, continuity, progress,
   setbacks, exceptions, and goal evolution.
5. **Recurring themes** - supported recurrence across distinct sessions,
   including contrasting evidence when available.
6. **Relevant context** - stable background and therapist-curated context
   that remains relevant but is usually less immediate.
7. **Evidence and review** - therapist-accepted claims grouped by their `Use as`
   categories, with access to every cited source.

Empty modules are not rendered. Their absence means that the current eligible
record does not yet support that presentation, not that the clinician must take
an action.

## 3. Evidence maturity

Session count establishes whether a synthesis operation is possible; it does
not force a module to appear.

| Evidence maturity | Eligible material |
| --- | --- |
| One source session | Clinical overview, current concerns and priorities, open threads, decisions, relevant context, strengths or resources when explicitly supported, and accepted evidence |
| Two source sessions | Change and continuity, continued or resolved threads, and carefully labeled emerging recurrence |
| Three source sessions | Stronger recurrence, early trajectory, exceptions or contradictions, and goal evolution |
| Four or more source sessions | Richer longitudinal synthesis when the evidence supports it; no module is automatically required |

Trajectory and recurring-theme modules require evidence from at least two
distinct sessions. Single-session observations remain session-scoped and must
not be phrased as longitudinal patterns.

### Section orientation and topic transitions

The clinical overview is always fully readable. Each synthesis section starts with
its identifier and colon, followed by single-line white topic cards. A short,
newly worded section summary stays visible below without a fade or height clamp.
Summaries are generated with the topic analyses in the same coordinated request,
limited to 280 characters per populated kind, and must not concatenate topic
sentences or introduce new interpretations. Older snapshots use a label-based
orientation until the next ordinary background refresh; viewing never generates.

Expanding moves each topic card along the straight vector from its measured
compact position to its own evidence-linked paragraph heading. Collapsing reverses
the transition. Reduced-motion preferences skip the animation. Expanded cards use
compact padding and paragraph gaps while preserving readable line spacing and
all existing evidence links.

## 4. Module contract

Every module follows the same information contract:

```ts
type InsightModule = {
  kind:
    | "clinical_overview"
    | "current_focus"
    | "change"
    | "recurring_themes"
    | "context_history"
    | "record_orientation"
    | "accepted_evidence";
  maturity: "single_session" | "emerging" | "longitudinal";
  priorityBucket: "immediate" | "active" | "background" | "record";
  summary: string;
  items: InsightItem[];
  displayMode: "compact" | "collapsible";
  sourceSessionCount: number;
  lastChangedAt?: string;
};
```

The generator produces source-grounded clinical synthesis and evidence
relationships. Application policy owns eligibility, stable semantic ordering,
default disclosure, stale-state handling, and how much content appears in a
preview. The model does not choose arbitrary page placement.

Until the persisted snapshot schema emits this contract directly, the client
may deterministically adapt existing insight kinds into modules. That adapter
must preserve the same eligibility and ordering rules.

## 5. Priority policy

An item must first pass source eligibility and lifecycle filtering. Hidden,
stale, disputed, rejected, superseded, or unfinalized material is excluded or
routed to an explicit historical review workflow rather than presented as the
current clinical picture.

Within an eligible module, higher placement is informed by:

- therapist acceptance, pinning, or explicit curation;
- current open or unresolved status;
- meaningful change since the prior eligible session;
- direct relevance to the upcoming clinical conversation;
- evidence strength and coverage;
- recency; and
- whether newer evidence supersedes the item.

The model may propose relevance, but model-assigned importance alone cannot
determine prominence. Deterministic policy and therapist controls remain
authoritative.

## 6. Disclosure behavior

Each populated module provides a title, one concise section-level synthesis, a
compact grid of the individual insight names represented by that synthesis,
expandable detail, and explicit source access. The persisted generator should
write the section synthesis directly. Existing snapshots may use a deterministic
fallback assembled from the first analysis sentence of each included item; this
fallback must not introduce a new interpretation.

The preferred clinician-facing section names are **Current focus**, **Changes
over time**, **Recurring themes**, and **Relevant context**. Synthesis modules
use `CollapsibleContentPanel`, including its fixed gradient and restrained blur.

The collapsed state shows the section synthesis followed by the insight-name
grid. The whole module remains one disclosure target; the name tiles do not
become nested expanders. On expansion, every named item returns as its distinct,
fully formatted evidence-linked card. The main takeaway stays readable without
expansion; blur may conceal supporting depth but never the only statement of an
actionable or current item.

The page should maintain stable semantic anchors as modules appear over time so
that increasing evidence enriches the workspace without making its structure
feel arbitrary.

The four synthesis modules—Current focus, Changes over time, Recurring themes,
and Relevant context—share one quiet parent surface. This visually identifies
them as facets of the same generated synthesis without removing their individual
cards or disclosure behavior.

During retrieval, the complete Insights hierarchy remains present. Section
titles stay readable while neutral blurred text streaks occupy the eventual copy
and metric positions. Loading placeholders preserve geometry, contain no
invented clinical language, respect reduced-motion preferences, and are replaced
in place when the validated snapshot arrives.

## 7. Evidence and language constraints

- Generated patterns are clinician review prompts, not diagnoses, risk
  determinations, or treatment decisions.
- Analysis prose remains distinct from contextual evidence prose.
- Evidence links attach to model-provided, phrase-level claims and exact source
  slices; the interface never infers anchors by lexical similarity.
- Contrasting evidence and exceptions remain available when they materially
  qualify a synthesis.
- Accepted therapist evidence remains inspectable at the bottom of the page and
  is not replaced by generated summaries.
- The pre-session brief remains a separate read-only condensation of the latest
  validated Insights snapshot.

## 8. Implementation sequence

1. Adapt current snapshot kinds into the stable module hierarchy and apply
   evidence-maturity filtering.
2. Reuse `CollapsibleContentPanel` for overview and module depth while keeping
   the first useful content visible.
3. Place compact at-a-glance metrics directly beneath the clinical overview.
4. Extend the persisted snapshot schema with explicit maturity, priority,
   source-session coverage, freshness, and supersession metadata.
5. Evaluate usefulness, grounding, omission behavior, correction propagation,
   and harmful-overreach cases with representative governed records.
