"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ApiError, api } from "@/lib/api";
import type { BriefEvidence, ClientJourneyEntry, LongitudinalRecordContext, PersistedInsightSnapshot } from "@/lib/types";

type Props = {
  onViewEvidence: (evidence: BriefEvidence) => void;
  recordContext?: LongitudinalRecordContext;
};

type InsightItem = PersistedInsightSnapshot["items"][number];

type InsightClaim = {
  phrase: string;
  occurrence: number;
  evidenceIds: string[];
};

type ThemeMetric = {
  key: string;
  label: string;
  sessionCount: number;
  momentCount: number;
};

const groups: Array<{ title: string; description: string; kinds: InsightItem["kind"][] }> = [
  { title: "Overall trajectory", description: "Evidence-linked changes or continuity across the relationship.", kinds: ["trajectory"] },
  { title: "Recurring themes", description: "Topics that appear across more than one part of the record.", kinds: ["theme"] },
  { title: "Open threads", description: "Items that may be useful to revisit in a future session.", kinds: ["open_thread"] },
  { title: "Context and history", description: "Relevant background and therapist-curated context.", kinds: ["relevant_history", "client_context", "therapist_curated"] },
];

function savedContentText(content: Record<string, unknown>) {
  for (const field of ["analysis", "text", "summary", "narrative", "title"]) {
    const value = content[field];
    if (typeof value === "string" && value.trim()) return value;
  }
  return "This saved item needs clinician review.";
}

function insightLabel(content: Record<string, unknown>) {
  if (typeof content.label === "string" && content.label.trim()) return content.label.trim();
  const firstSentence = savedContentText(content).split(/(?<=[.!?])\s/u, 1)[0].trim();
  return firstSentence.length > 78 ? `${firstSentence.slice(0, 75).trimEnd()}…` : firstSentence;
}

function contentContexts(content: Record<string, unknown>): Array<Record<string, unknown>> {
  if (!Array.isArray(content.contexts)) return [];
  return content.contexts.filter((value): value is Record<string, unknown> => Boolean(value) && typeof value === "object" && typeof (value as Record<string, unknown>).text === "string");
}

function evidenceSources(item: InsightItem, evidenceIds?: string[]): BriefEvidence[] {
  const allowed = evidenceIds ? new Set(evidenceIds) : null;
  return item.evidence.flatMap((source) => source.transcript_segment_id && source.session_id && (!allowed || allowed.has(source.transcript_segment_id)) ? [{
    evidence_id: source.transcript_segment_id,
    session_id: `session-${source.session_id}`,
    session_label: source.session_label ?? "Completed session",
    segment_index: source.segment_index,
    start: source.start,
    end: source.end,
    quote: source.quote,
  }] : []);
}

function evidenceLabel(label: string) {
  const parts = label.split(" · ");
  return parts[0] === "Synthetic" && parts.length > 2 ? parts.slice(2).join(" · ") : label;
}

function contentClaims(content: Record<string, unknown>): InsightClaim[] {
  if (!Array.isArray(content.claims)) return [];
  return content.claims.flatMap((value) => {
    if (!value || typeof value !== "object") return [];
    const claim = value as Record<string, unknown>;
    if (typeof claim.phrase !== "string" || !claim.phrase.trim()) return [];
    if (claim.occurrence !== undefined && (!Number.isInteger(claim.occurrence) || Number(claim.occurrence) < 0)) return [];
    if (!Array.isArray(claim.evidence_ids) || !claim.evidence_ids.length || !claim.evidence_ids.every((id) => typeof id === "string" && id)) return [];
    return [{ phrase: claim.phrase, occurrence: Number(claim.occurrence ?? 0), evidenceIds: claim.evidence_ids as string[] }];
  });
}

function EvidenceDialogLink({ phrase, sources, onViewEvidence, fallback = false }: { phrase: string; sources: BriefEvidence[]; onViewEvidence: Props["onViewEvidence"]; fallback?: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const sourceLabel = sources.length === 1 ? "1 source" : `${sources.length} sources`;
  return <>
    <a href={`#${titleId}`} onClick={(event) => { event.preventDefault(); dialog.current?.showModal(); }} aria-haspopup="dialog" aria-controls={titleId} aria-label={`View evidence for ${phrase}`} className={`${fallback ? "ml-1 align-baseline text-xs font-semibold text-stone-700 underline decoration-stone-400 underline-offset-3 hover:text-stone-950" : "font-bold text-inherit no-underline hover:text-stone-950"} cursor-grab rounded-sm text-left transition-colors active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700`}>
      {fallback ? `View ${sourceLabel}` : phrase}
    </a>
    {typeof document !== "undefined" && createPortal(<dialog id={titleId} ref={dialog} aria-labelledby={`${titleId}-heading`} onClick={(event) => { if (event.target === event.currentTarget) dialog.current?.close(); }} className="m-auto max-h-[85vh] w-[min(92vw,640px)] overflow-y-auto rounded-2xl border border-stone-300 bg-white p-6 text-left text-stone-800 shadow-xl backdrop:bg-stone-950/50">
      <div className="flex items-start justify-between gap-4">
        <div><h3 id={`${titleId}-heading`} className="text-base font-semibold">Evidence in context</h3><p className="mt-1 text-xs text-stone-500">Supporting slices for this linked statement.</p></div>
        <button type="button" onClick={() => dialog.current?.close()} aria-label="Close evidence" className="cursor-grab rounded-lg px-2 text-xl active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">×</button>
      </div>
      <p className="my-4 border-l-2 border-emerald-300 pl-4 text-base font-semibold leading-7 text-stone-800">{phrase}</p>
      <div className="grid gap-3">
        {sources.map((source) => <article key={source.evidence_id} className="rounded-xl border border-stone-300 bg-stone-50 p-4 text-sm leading-6">
          <p className="font-semibold text-stone-800">{evidenceLabel(source.session_label)}</p>
          {source.quote ? <p className="mt-2 text-stone-700">“{source.quote}”</p> : <p className="mt-2 text-stone-500">This source is linked to the transcript segment.</p>}
          <button type="button" onClick={() => { dialog.current?.close(); onViewEvidence(source); }} className="mt-3 cursor-grab rounded-lg border border-stone-300 bg-white px-3 py-1.5 font-semibold text-emerald-800 transition-colors hover:bg-stone-100 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Open transcript evidence</button>
        </article>)}
      </div>
    </dialog>, document.body)}
  </>;
}

function needsInlineSpace(left: string, right: string) {
  return Boolean(left && right && !/\s$/u.test(left) && !/^\s/u.test(right) && /[\p{L}\p{N}]$/u.test(left) && /^[\p{L}\p{N}]/u.test(right));
}

function phraseForSentencePosition(phrase: string, precedingText: string) {
  const trimmedPrefix = precedingText.trimEnd();
  const startsSentence = !trimmedPrefix || /[.!?]["'’”\])}]*$/u.test(trimmedPrefix);
  const firstLetter = phrase.search(/\p{L}/u);
  if (firstLetter < 0) return phrase;

  const word = phrase.slice(firstLetter).match(/^\p{L}+/u)?.[0] ?? "";
  if (!startsSentence && (word === "I" || (word.length > 1 && word === word.toLocaleUpperCase()))) return phrase;

  const letter = phrase[firstLetter];
  const casedLetter = startsSentence ? letter.toLocaleUpperCase() : letter.toLocaleLowerCase();
  return phrase.slice(0, firstLetter) + casedLetter + phrase.slice(firstLetter + letter.length);
}

function EvidenceLinkedText({ content, item, onViewEvidence }: { content: Record<string, unknown>; item: InsightItem; onViewEvidence: Props["onViewEvidence"] }) {
  const text = savedContentText(content);
  const spans = contentClaims(content).map((claim) => {
    let start = -1;
    for (let index = 0; index <= claim.occurrence; index += 1) {
      start = text.indexOf(claim.phrase, start + 1);
      if (start < 0) break;
    }
    return { ...claim, start, end: start + claim.phrase.length, sources: evidenceSources(item, claim.evidenceIds) };
  }).sort((left, right) => left.start - right.start);
  const valid = spans.length > 0 && spans.every((span, index) => span.start >= 0 && span.sources.length > 0 && (!index || span.start >= spans[index - 1].end));

  if (!valid) {
    const sources = evidenceSources(item);
    return <>{text}{sources.length ? <> <EvidenceDialogLink phrase={text} sources={sources} onViewEvidence={onViewEvidence} fallback /></> : null}</>;
  }

  return <>
    {spans.map((span, index) => {
      const before = text.slice(index ? spans[index - 1].end : 0, span.start);
      const after = text.slice(span.end);
      const displayPhrase = phraseForSentencePosition(span.phrase, text.slice(0, span.start));
      return <span key={`${span.start}-${span.end}`}>
        {before}{needsInlineSpace(before, displayPhrase) ? " " : null}
        <EvidenceDialogLink phrase={displayPhrase} sources={span.sources} onViewEvidence={onViewEvidence} />
        {needsInlineSpace(displayPhrase, after) ? " " : null}
      </span>;
    })}
    {text.slice(spans[spans.length - 1].end)}
  </>;
}

function StatCard({ value, label, detail }: { value: number; label: string; detail: string }) {
  return <article className="rounded-xl border border-stone-300 bg-stone-50 p-4">
    <p className="text-2xl font-semibold tracking-tight text-stone-900">{value}</p>
    <h3 className="mt-1 text-sm font-semibold text-stone-800">{label}</h3>
    <p className="mt-1 text-xs leading-5 text-stone-500">{detail}</p>
  </article>;
}

function ThemeRecurrence({ themes }: { themes: ThemeMetric[] }) {
  const maximumMoments = Math.max(1, ...themes.map((theme) => theme.momentCount));
  return <section className="mt-5 rounded-xl border border-stone-300 bg-stone-50 p-4" aria-labelledby="theme-recurrence-heading">
    <div className="flex items-baseline justify-between gap-3">
      <h3 id="theme-recurrence-heading" className="text-sm font-semibold text-stone-900">Theme recurrence</h3>
      <span className="text-xs text-stone-500">Cited record moments</span>
    </div>
    {themes.length ? <div className="mt-4 grid gap-4">
      {themes.map((theme) => <div key={theme.key} className="grid gap-2 sm:grid-cols-[minmax(150px,0.8fr)_minmax(180px,1.2fr)_auto] sm:items-center">
        <p className="truncate text-sm font-medium text-stone-800" title={theme.label}>{theme.label}</p>
        <div className="h-2 overflow-hidden rounded-full border border-stone-300 bg-white" aria-hidden="true">
          <div className="h-full min-w-2 rounded-full bg-emerald-800/70" style={{ width: `${Math.max(8, (theme.momentCount / maximumMoments) * 100)}%` }} />
        </div>
        <p className="text-xs tabular-nums text-stone-600 sm:min-w-28 sm:text-right">{theme.sessionCount} {theme.sessionCount === 1 ? "session" : "sessions"} · {theme.momentCount} {theme.momentCount === 1 ? "moment" : "moments"}</p>
      </div>)}
    </div> : <p className="mt-3 text-sm text-stone-600">No recurring themes are in view yet.</p>}
  </section>;
}

function InsightCard({ item, onViewEvidence }: { item: InsightItem; onViewEvidence: Props["onViewEvidence"] }) {
  const analysis = savedContentText(item.content);
  const contexts = contentContexts(item.content);
  const legacySources = evidenceSources(item);
  const contextLength = contexts.reduce((length, context) => length + savedContentText(context).length, 0);
  const useSecondParagraph = analysis.length + contextLength > 620;
  const contextualProse = contexts.map((context, index) => <span key={index}>{index ? " " : null}<EvidenceLinkedText content={context} item={item} onViewEvidence={onViewEvidence} /></span>);
  return <article className="rounded-xl border border-stone-300 bg-stone-50 p-4">
    <h3 className="text-sm font-semibold text-stone-800">{insightLabel(item.content)}</h3>
    <div className="mt-3 text-[15px] leading-7 text-stone-800 [text-wrap:pretty]">
      <p>{analysis}{contexts.length && !useSecondParagraph ? <> {contextualProse}</> : null}{!contexts.length && legacySources.length ? <> The supporting record is available across {legacySources.length === 1 ? "one cited moment" : `${legacySources.length} cited moments`}. <EvidenceDialogLink phrase={analysis} sources={legacySources} onViewEvidence={onViewEvidence} fallback /></> : null}</p>
      {contexts.length && useSecondParagraph ? <p className="mt-3">{contextualProse}</p> : null}
    </div>
  </article>;
}

function JourneyInsightCard({ entry, onViewEvidence }: { entry: ClientJourneyEntry; onViewEvidence: Props["onViewEvidence"] }) {
  const sources = entry.evidence;
  return <article className="rounded-xl border border-stone-300 bg-stone-50 p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-stone-500">{entry.status === "proposed" ? "Awaiting therapist review" : "Therapist accepted"}</p>
      <p className="text-xs text-stone-500">{sources.length} {sources.length === 1 ? "source" : "sources"}</p>
    </div>
    <p className="mt-3 text-[15px] leading-7 text-stone-800 [text-wrap:pretty]">{entry.text} <EvidenceDialogLink phrase={entry.text} sources={sources} onViewEvidence={onViewEvidence} fallback /></p>
  </article>;
}

function InsightGroup({ title, description, items, onViewEvidence }: { title: string; description: string; items: InsightItem[]; onViewEvidence: Props["onViewEvidence"] }) {
  return <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
      <h2 className="text-base font-semibold text-stone-900">{title}</h2>
      <p className="text-xs leading-5 text-stone-500">{description}</p>
    </div>
    {items.length ? <div className="mt-4 grid gap-3">{items.map((item) => <InsightCard key={item.id} item={item} onViewEvidence={onViewEvidence} />)}</div> : <p className="mt-4 rounded-xl border border-dashed border-stone-300 bg-stone-50 px-4 py-5 text-sm text-stone-600">Nothing is currently saved in this area.</p>}
  </section>;
}

function InsightsWorkspace({ snapshot, entries, onViewEvidence }: { snapshot: PersistedInsightSnapshot | null; entries: ClientJourneyEntry[]; onViewEvidence: Props["onViewEvidence"] }) {
  const visibleItems = useMemo(() => snapshot?.items.filter((item) => {
    if (item.review_state === "hidden") return false;
    const sessionCount = new Set(item.evidence.map((source) => source.session_id).filter(Boolean)).size;
    if (item.kind === "trajectory" || item.kind === "theme") return sessionCount >= 2;
    return sessionCount >= 1;
  }) ?? [], [snapshot]);
  const currentItems = visibleItems.filter((item) => item.review_state !== "stale" && item.review_state !== "disputed");
  const reviewableJourney = entries.filter((entry) => (entry.status === "accepted" || entry.status === "proposed") && entry.evidence.length > 0);
  const openJourney = reviewableJourney.filter((entry) => entry.category === "open_thread");
  const sessionObservations = reviewableJourney.filter((entry) => entry.category !== "open_thread");
  const representedSessions = new Set([
    ...visibleItems.flatMap((item) => item.evidence.map((source) => source.session_id).filter(Boolean)),
    ...reviewableJourney.flatMap((entry) => entry.evidence.map((source) => source.session_id).filter(Boolean)),
  ]).size;
  const snapshotThemes = currentItems.filter((item) => item.kind === "theme");
  const themeMetrics: ThemeMetric[] = snapshotThemes.length ? snapshotThemes.map((item) => {
    const sessions = new Set(item.evidence.map((source) => source.session_id).filter(Boolean));
    const moments = new Set(item.evidence.map((source) => source.transcript_segment_id ?? source.clinical_note_version_id).filter(Boolean));
    return { key: item.id, label: insightLabel(item.content), sessionCount: sessions.size, momentCount: moments.size };
  }) : [];
  const themeCount = themeMetrics.length;
  const openThreadCount = currentItems.filter((item) => item.kind === "open_thread").length + openJourney.length;
  const awaitingReview = currentItems.filter((item) => item.review_state === "draft").length + entries.filter((entry) => entry.status === "proposed").length;
  const visibleGroups = groups.map((group) => ({ ...group, items: visibleItems.filter((item) => group.kinds.includes(item.kind)) })).filter((group) => group.items.length > 0);
  const hasEvidence = representedSessions > 0;

  return <section className="text-left" aria-label="Clinical insights workspace">
    <header className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
      <h2 className="text-xl font-semibold tracking-tight text-stone-900">Insights</h2>
      <section className="mt-5" aria-labelledby="longitudinal-overview-heading">
        <h3 id="longitudinal-overview-heading" className="text-base font-semibold text-stone-900">Longitudinal overview</h3>
        <p className="mt-3 max-w-4xl text-[15px] leading-7 text-stone-700">{snapshot ? savedContentText(snapshot.content) : reviewableJourney.length ? "Source-linked material from completed sessions is ready for therapist review. Cross-session trajectory and recurring-theme cards will appear only when they have evidence from at least two sessions." : "No source-linked session material is available yet."}</p>
        {snapshot ? <p className="mt-4 text-xs leading-5 text-stone-500">Workspace {snapshot.status} · version {snapshot.version} · generated by {snapshot.generator_name}. Review the cited evidence before relying on generated observations.</p> : null}
      </section>
    </header>

    {hasEvidence ? <section className="mt-6 rounded-2xl border border-stone-300 bg-white p-5 shadow-sm" aria-label="Insight metrics">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard value={representedSessions} label="Evidence sessions" detail="Sessions cited by the current workspace." />
        {themeCount > 0 ? <StatCard value={themeCount} label="Themes in view" detail="Themes supported across sessions." /> : null}
        {openThreadCount > 0 ? <StatCard value={openThreadCount} label="Open threads" detail="Items that may need follow-up." /> : null}
        {awaitingReview > 0 ? <StatCard value={awaitingReview} label="Awaiting review" detail="Proposals requiring therapist judgment." /> : null}
      </div>
      {themeMetrics.length ? <ThemeRecurrence themes={themeMetrics} /> : null}
      <p className="mt-3 text-xs leading-5 text-stone-500">These counts organize the available record; they are not clinical scores or conclusions.</p>
    </section> : null}

    <div className="mt-6 grid gap-4 lg:grid-cols-2">
      {visibleGroups.map((group) => <InsightGroup key={group.title} title={group.title} description={group.description} items={group.items} onViewEvidence={onViewEvidence} />)}
      {openJourney.length ? <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-stone-900">Open threads</h2>
        <p className="mt-1 text-xs leading-5 text-stone-500">Source-linked items that may be useful to revisit.</p>
        <div className="mt-4 grid gap-3">{openJourney.map((entry) => <JourneyInsightCard key={entry.id} entry={entry} onViewEvidence={onViewEvidence} />)}</div>
      </section> : null}
      {sessionObservations.length ? <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-stone-900">Session observations</h2>
        <p className="mt-1 text-xs leading-5 text-stone-500">Cited session material. Proposed items remain unapproved until a therapist reviews them.</p>
        <div className="mt-4 grid gap-3">{sessionObservations.map((entry) => <JourneyInsightCard key={entry.id} entry={entry} onViewEvidence={onViewEvidence} />)}</div>
      </section> : null}
    </div>
  </section>;
}

export function ClientInsights({ onViewEvidence, recordContext }: Props) {
  const [snapshot, setSnapshot] = useState<PersistedInsightSnapshot | null>(null);
  const [entries, setEntries] = useState<ClientJourneyEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!recordContext) return;
    let cancelled = false;
    const snapshotRequest = api.getLatestInsightSnapshot(recordContext.organizationId, recordContext.clientId)
      .catch((reason: unknown) => {
        if (reason instanceof ApiError && reason.status === 404) return null;
        throw reason;
      });
    void Promise.all([snapshotRequest, api.getClientJourney(recordContext.organizationId, recordContext.clientId)])
      .then(([nextSnapshot, journey]) => { if (!cancelled) { setSnapshot(nextSnapshot); setEntries(journey.entries); setError(null); } })
      .catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load the clinical insights workspace."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [recordContext]);

  if (!recordContext) return <section className="rounded-2xl border border-stone-300 bg-white p-5 text-left shadow-sm"><h2 className="text-lg font-semibold text-stone-900">Insights</h2><p className="mt-3 text-sm text-stone-600">Open Insights from an authorized client workspace.</p></section>;
  if (error) return <section className="rounded-2xl border border-stone-300 bg-white p-5 text-left shadow-sm"><h2 className="text-lg font-semibold text-stone-900">Insights</h2><p className="mt-3 text-sm text-red-700">{error}</p></section>;
  if (loading) return <section className="rounded-2xl border border-stone-300 bg-white p-5 text-left shadow-sm"><h2 className="text-lg font-semibold text-stone-900">Insights</h2><p className="mt-3 text-sm text-stone-600">Preparing the longitudinal record…</p></section>;
  return <InsightsWorkspace snapshot={snapshot} entries={entries} onViewEvidence={onViewEvidence} />;
}
