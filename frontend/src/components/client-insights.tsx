"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CollapsibleContentPanel } from "@/components/collapsible-content-panel";
import { TextLoadingSkeleton } from "@/components/text-loading-skeleton";
import { ApiError, api } from "@/lib/api";
import type { BriefEvidence, ClientJourneyEntry, InsightsRefreshStatus, LongitudinalRecordContext, PersistedInsightSnapshot } from "@/lib/types";

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

type InsightModuleKind = "current_focus" | "change" | "recurring_themes" | "context_history";
type InsightMaturity = "single_session" | "emerging" | "longitudinal";
type InsightPriorityBucket = "immediate" | "active" | "background";

function insightTimestamp(value: string, now: number) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return null;
  const minutes = Math.max(0, Math.floor((now - date.getTime()) / 60_000));
  const relative = minutes < 1
    ? "less than a minute ago"
    : minutes < 60
      ? `${minutes} ${minutes === 1 ? "minute" : "minutes"} ago`
      : minutes < 1440
        ? `${Math.floor(minutes / 60)} ${Math.floor(minutes / 60) === 1 ? "hour" : "hours"} ago`
        : `${Math.floor(minutes / 1440)} ${Math.floor(minutes / 1440) === 1 ? "day" : "days"} ago`;
  const absolute = new Intl.DateTimeFormat(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit",
  }).format(date);
  return { absolute, relative };
}

function InsightsFreshness({ status, snapshot }: { status: InsightsRefreshStatus | null; snapshot: PersistedInsightSnapshot | null }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);
  const publishedAt = status?.last_published_at ?? snapshot?.created_at;
  if (!publishedAt) return null;
  const timestamp = insightTimestamp(publishedAt, now);
  if (!timestamp) return null;
  return (
    <p className="text-right text-xs leading-5 text-stone-500">
      <time dateTime={publishedAt}>
        Last updated {timestamp.relative} ({timestamp.absolute})
      </time>
    </p>
  );
}

type InsightModule = {
  kind: InsightModuleKind;
  title: string;
  previewSummary: string;
  maturity: InsightMaturity;
  priorityBucket: InsightPriorityBucket;
  sourceSessionCount: number;
  items: InsightItem[];
  displayMode: "compact" | "collapsible";
};

const moduleDefinitions: Array<{
  kind: InsightModuleKind;
  title: string;
  priorityBucket: InsightPriorityBucket;
  kinds: InsightItem["kind"][];
}> = [
  { kind: "current_focus", title: "Current focus", priorityBucket: "immediate", kinds: ["open_thread"] },
  { kind: "change", title: "Changes over time", priorityBucket: "active", kinds: ["trajectory"] },
  { kind: "recurring_themes", title: "Recurring themes", priorityBucket: "active", kinds: ["theme"] },
  { kind: "context_history", title: "Relevant context", priorityBucket: "background", kinds: ["relevant_history", "client_context", "therapist_curated"] },
];

function sourceSessionCount(items: InsightItem[]) {
  return new Set(items.flatMap((item) => item.evidence.map((source) => source.session_id).filter((sessionId): sessionId is string => Boolean(sessionId)))).size;
}

function moduleMaturity(sessionCount: number): InsightMaturity {
  if (sessionCount <= 1) return "single_session";
  if (sessionCount <= 3) return "emerging";
  return "longitudinal";
}

function firstSentence(text: string) {
  return text.trim().split(/(?<=[.!?])\s/u, 1)[0].trim();
}

function truncateAtWord(text: string, maximumLength: number) {
  if (text.length <= maximumLength) return text;
  const candidate = text.slice(0, Math.max(0, maximumLength - 1));
  const lastSpace = candidate.lastIndexOf(" ");
  return `${candidate.slice(0, lastSpace > maximumLength * 0.6 ? lastSpace : candidate.length).trimEnd()}…`;
}

function modulePreviewSummary(items: InsightItem[]) {
  const maximumTotalLength = 420;
  const perItemLength = Math.max(88, Math.floor(maximumTotalLength / items.length));
  return items.map((item) => truncateAtWord(firstSentence(savedContentText(item.content)), perItemLength)).join(" ");
}

function buildInsightModules(items: InsightItem[]): InsightModule[] {
  return moduleDefinitions.flatMap((definition) => {
    const moduleItems = items
      .filter((item) => definition.kinds.includes(item.kind))
      .sort((left, right) => {
        const reviewPriority = (item: InsightItem) => item.review_state === "accepted" ? 0 : 1;
        return reviewPriority(left) - reviewPriority(right) || left.display_order - right.display_order;
      });
    if (!moduleItems.length) return [];
    const sessions = sourceSessionCount(moduleItems);
    return [{
      ...definition,
      previewSummary: modulePreviewSummary(moduleItems),
      maturity: moduleMaturity(sessions),
      sourceSessionCount: sessions,
      items: moduleItems,
      displayMode: "collapsible",
    }];
  });
}

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
  return item.evidence.flatMap((source) => {
    const evidenceId = source.transcript_segment_id || source.clinical_note_version_id;
    if (!evidenceId || !source.session_id || (allowed && !allowed.has(evidenceId))) return [];
    return [{
      evidence_id: evidenceId,
      clinical_note_version_id: source.clinical_note_version_id,
      note_text: source.note_text,
      session_id: `session-${source.session_id}`,
      session_label: source.session_label ?? "Completed session",
      segment_index: source.segment_index,
      start: source.start,
      end: source.end,
      quote: source.quote,
    }];
  });
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

// Select verbatim note sentences locally; never invent a supporting quotation.
function relevantNoteExcerpt(note: string | undefined, phrase: string) {
  if (!note?.trim()) return null;
  const words = (text: string) => text.toLocaleLowerCase().match(/[\p{L}\p{N}]{4,}/gu) ?? [];
  const terms = new Set(words(phrase));
  const sentences = note.match(/[^.!?\n]+(?:[.!?]+|$)/gu) ?? [];
  const ranked = sentences.map((text, index) => ({
    text: text.trim(), index,
    score: new Set(words(text).filter((word) => terms.has(word))).size,
  })).filter((sentence) => sentence.score > 0).sort((a, b) => b.score - a.score || a.index - b.index);
  const excerpt = ranked.slice(0, 2).sort((a, b) => a.index - b.index).map(({ text }) => text).join(" … ");
  return excerpt ? truncateAtWord(excerpt, 700) : null;
}

function EvidenceDialogLink({ phrase, sources, onViewEvidence, fallback = false, interpretation = false }: { phrase: string; sources: BriefEvidence[]; onViewEvidence: Props["onViewEvidence"]; fallback?: boolean; interpretation?: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [sourceIndex, setSourceIndex] = useState(0);
  const titleId = useId();
  const sourceLabel = sources.length === 1 ? "1 source" : `${sources.length} sources`;
  return <>
    <a href={`#${titleId}`} onClick={(event) => { event.preventDefault(); setSourceIndex(0); dialog.current?.showModal(); }} aria-haspopup="dialog" aria-controls={titleId} aria-label={`View evidence for ${phrase}`} className={`${fallback ? "ml-1 align-baseline text-xs font-semibold text-stone-700 underline decoration-stone-400 underline-offset-3 hover:text-stone-950" : "font-bold text-inherit no-underline hover:text-stone-950"} cursor-grab rounded-sm text-left transition-colors active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700`}>
      {fallback ? `View ${sourceLabel}` : phrase}
    </a>
    {typeof document !== "undefined" && createPortal(<dialog id={titleId} ref={dialog} aria-labelledby={`${titleId}-heading`} onClick={(event) => { if (event.target === event.currentTarget) dialog.current?.close(); }} className="m-auto max-h-[85vh] w-[min(92vw,640px)] overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden rounded-2xl border border-stone-300 bg-white p-6 text-left text-stone-800 shadow-xl backdrop:bg-stone-950/50">
      <div className="flex items-start justify-between gap-4">
        <div><h3 id={`${titleId}-heading`} className="text-base font-semibold">Evidence in context</h3><p className="mt-1 text-xs text-stone-500">{interpretation ? "These records support a generated interpretation for clinician review; the interpretation is not a verbatim statement or established conclusion." : "Supporting slices for this linked statement."}</p></div>
        <button type="button" onClick={() => dialog.current?.close()} aria-label="Close evidence" className="cursor-grab rounded-lg px-2 text-xl active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">×</button>
      </div>
      <p className="my-4 border-l-2 border-emerald-300 pl-4 text-base font-semibold leading-7 text-stone-800">{phrase}</p>
      <div className="grid gap-3">
        {sources.slice(sourceIndex, sourceIndex + 1).map((source) => <article key={source.evidence_id} className="rounded-xl border border-stone-300 bg-stone-50 p-4 text-sm leading-6">
          <p className="font-semibold text-stone-800">{evidenceLabel(source.session_label)}</p>
          {source.clinical_note_version_id ? <p className="mt-2 whitespace-pre-wrap text-stone-700">Finalized clinical note — relevant excerpt: {relevantNoteExcerpt(source.note_text, phrase) ?? "No specific matching passage is available for this claim. Review the finalized note in the session record."}</p> : source.quote ? <p className="mt-2 text-stone-700">“{source.quote}”</p> : <p className="mt-2 text-stone-500">This source is linked to the transcript segment.</p>}
          {!source.clinical_note_version_id && <button type="button" onClick={() => { dialog.current?.close(); onViewEvidence(source); }} className="mt-3 cursor-grab rounded-lg border border-stone-300 bg-white px-3 py-1.5 font-semibold text-emerald-800 transition-colors hover:bg-stone-100 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Open transcript evidence</button>}
        </article>)}
      </div>
      {sources.length > 1 && <nav aria-label="Evidence sources" className="mt-4 flex items-center justify-between gap-3 text-sm">
        <button type="button" disabled={sourceIndex === 0} onClick={() => setSourceIndex((index) => index - 1)} className="cursor-grab rounded-lg border border-stone-300 px-3 py-2 active:cursor-grabbing disabled:cursor-default disabled:opacity-40">Previous</button>
        <span aria-live="polite">Source {sourceIndex + 1} of {sources.length}</span>
        <button type="button" disabled={sourceIndex === sources.length - 1} onClick={() => setSourceIndex((index) => index + 1)} className="cursor-grab rounded-lg border border-stone-300 px-3 py-2 active:cursor-grabbing disabled:cursor-default disabled:opacity-40">Next</button>
      </nav>}
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

function EvidenceLinkedText({ content, item, onViewEvidence, interpretation = false }: { interpretation?: boolean; content: Record<string, unknown>; item: InsightItem; onViewEvidence: Props["onViewEvidence"] }) {
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
    return <>{text}{sources.length ? <> <EvidenceDialogLink phrase={text} sources={sources} onViewEvidence={onViewEvidence} interpretation={interpretation} fallback /></> : null}</>;
  }

  return <>
    {spans.map((span, index) => {
      const before = text.slice(index ? spans[index - 1].end : 0, span.start);
      const after = text.slice(span.end);
      const displayPhrase = phraseForSentencePosition(span.phrase, text.slice(0, span.start));
      return <span key={`${span.start}-${span.end}`}>
        {before}{needsInlineSpace(before, displayPhrase) ? " " : null}
        <EvidenceDialogLink phrase={displayPhrase} sources={span.sources} onViewEvidence={onViewEvidence} interpretation={interpretation} />
        {needsInlineSpace(displayPhrase, after) ? " " : null}
      </span>;
    })}
    {text.slice(spans[spans.length - 1].end)}
  </>;
}

function StatCard({ value, label, detail }: { value: number; label: string; detail: string }) {
  return <article className="rounded-xl border border-stone-300 bg-stone-50 px-3.5 py-3">
    <div className="flex items-baseline gap-2">
      <p className="text-xl font-semibold tracking-tight text-stone-900">{value}</p>
      <h3 className="text-sm font-semibold text-stone-800">{label}</h3>
    </div>
    <p className="mt-0.5 text-xs leading-4 text-stone-500">{detail}</p>
  </article>;
}

function ThemeRecurrence({ themes }: { themes: ThemeMetric[] }) {
  const maximumMoments = Math.max(1, ...themes.map((theme) => theme.momentCount));
  return <section className="mt-3 rounded-xl border border-stone-300 bg-stone-50 p-3.5" aria-labelledby="theme-recurrence-heading">
    <div className="flex items-baseline justify-between gap-3">
      <h3 id="theme-recurrence-heading" className="text-sm font-semibold text-stone-900">Theme recurrence</h3>
      <span className="text-xs text-stone-500">Cited record moments</span>
    </div>
    {themes.length ? <div className="mt-3 grid gap-3">
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
      <p>{Array.isArray(item.content.analysis_claims) ? <EvidenceLinkedText content={{ text: analysis, claims: item.content.analysis_claims }} item={item} onViewEvidence={onViewEvidence} interpretation /> : analysis}{contexts.length && !useSecondParagraph ? <> {contextualProse}</> : null}{!contexts.length && !Array.isArray(item.content.analysis_claims) && legacySources.length ? <> The supporting record is available across {legacySources.length === 1 ? "one cited moment" : `${legacySources.length} cited moments`}. <EvidenceDialogLink phrase={analysis} sources={legacySources} onViewEvidence={onViewEvidence} fallback /></> : null}</p>
      {contexts.length && useSecondParagraph ? <p className="mt-3">{contextualProse}</p> : null}
    </div>
  </article>;
}

function InsightModuleBody({ items, onViewEvidence, className = "" }: { items: InsightItem[]; onViewEvidence: Props["onViewEvidence"]; className?: string }) {
  return <div className={`grid gap-3 ${className}`}>{items.map((item) => <InsightCard key={item.id} item={item} onViewEvidence={onViewEvidence} />)}</div>;
}

function InsightModulePreview({ module }: { module: InsightModule }) {
  return <div className="px-4 pb-4">
    <p className="text-sm leading-6 text-stone-700 [text-wrap:pretty]">{module.previewSummary}</p>
    <div className="mt-3 grid gap-2 sm:grid-cols-2">
      {module.items.map((item) => <span key={item.id} className="rounded-xl border border-stone-300 bg-stone-50 px-3 py-2.5 text-sm font-semibold leading-5 text-stone-800 shadow-sm">
        {insightLabel(item.content)}
      </span>)}
    </div>
  </div>;
}

function InsightGroup({ module, onViewEvidence }: { module: InsightModule; onViewEvidence: Props["onViewEvidence"] }) {
  if (module.displayMode === "collapsible") {
    const body = <InsightModuleBody items={module.items} onViewEvidence={onViewEvidence} className="p-4 pt-0" />;
    return <CollapsibleContentPanel
      title={module.title}
      preview={`${module.previewSummary} ${module.items.map((item) => insightLabel(item.content)).join(". ")}`}
      previewContent={<InsightModulePreview module={module} />}
      collapsedPreviewHeight={152}
      className="rounded-2xl border-stone-300 bg-white shadow-sm"
      ariaLabel={`${module.title}, ${module.sourceSessionCount} source ${module.sourceSessionCount === 1 ? "session" : "sessions"}`}
    >
      <div className="border-t border-stone-200">{body}</div>
    </CollapsibleContentPanel>;
  }

  return <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
    <h2 className="text-base font-semibold text-stone-900">{module.title}</h2>
    <InsightModuleBody items={module.items} onViewEvidence={onViewEvidence} className="mt-4" />
  </section>;
}

function InsightSectionLoadingSkeleton({ title }: { title: string }) {
  return <section className="rounded-2xl border border-stone-300 bg-white p-4 shadow-sm">
    <h2 className="text-base font-semibold text-stone-900">{title}</h2>
    <TextLoadingSkeleton className="mt-4" label={`Loading ${title.toLowerCase()}`} widths={["92%", "78%"]} />
    <div className="mt-4 grid gap-2 sm:grid-cols-2" aria-hidden="true">
      <span className="h-10 rounded-xl border border-stone-300 bg-stone-50 p-3"><span className="text-loading-streak block w-3/4" /></span>
      <span className="h-10 rounded-xl border border-stone-300 bg-stone-50 p-3"><span className="text-loading-streak block w-2/3" /></span>
    </div>
  </section>;
}

function InsightsLoadingSkeleton() {
  return <section className="space-y-4 text-left" aria-label="Loading clinical insights workspace" aria-busy="true">
    <h2 className="text-2xl font-semibold tracking-tight text-stone-900">Clinical Overview</h2>
    <section className="rounded-2xl border border-stone-300 bg-white p-4 shadow-sm">
      <TextLoadingSkeleton label="Loading clinical overview" widths={["96%", "89%", "71%"]} />
    </section>
    <section className="rounded-2xl border border-stone-300 bg-white p-4 shadow-sm" aria-label="Loading at-a-glance insight metrics">
      <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
        {["Themes in view", "Open threads", "Awaiting review", "Accepted evidence"].map((label, index) => <article key={label} className="rounded-xl border border-stone-300 bg-stone-50 px-3.5 py-3">
          <div className="flex items-center gap-2"><span className="text-loading-streak block w-6" /><span className="text-sm font-semibold text-stone-800">{label}</span></div>
          <span aria-hidden="true" className="text-loading-streak mt-2 block" style={{ width: index % 2 ? "72%" : "84%" }} />
        </article>)}
      </div>
      <div className="mt-3 rounded-xl border border-stone-300 bg-stone-50 p-3.5">
        <h3 className="text-sm font-semibold text-stone-900">Theme recurrence</h3>
        <TextLoadingSkeleton className="mt-3" label="Loading theme recurrence" widths={["88%", "76%"]} />
      </div>
    </section>
    <section aria-label="Loading synthesis sections">
      <div className="grid gap-4">
        {["Current focus", "Changes over time", "Recurring themes", "Relevant context"].map((title) => <InsightSectionLoadingSkeleton key={title} title={title} />)}
      </div>
    </section>
  </section>;
}

function InsightsWorkspace({ snapshot, entries, refreshStatus, onViewEvidence }: { snapshot: PersistedInsightSnapshot | null; entries: ClientJourneyEntry[]; refreshStatus: InsightsRefreshStatus | null; onViewEvidence: Props["onViewEvidence"] }) {
  const visibleItems = useMemo(() => snapshot?.items.filter((item) => {
    if (item.review_state === "hidden") return false;
    const sessionCount = new Set(item.evidence.map((source) => source.session_id).filter(Boolean)).size;
    if (item.kind === "trajectory" || item.kind === "theme") return sessionCount >= 2;
    return sessionCount >= 1;
  }) ?? [], [snapshot]);
  const currentItems = visibleItems.filter((item) => item.review_state !== "stale" && item.review_state !== "disputed");
  const acceptedJourney = entries.filter((entry) => entry.status === "accepted" && entry.evidence.length > 0);
  const snapshotThemes = currentItems.filter((item) => item.kind === "theme");
  const themeMetrics: ThemeMetric[] = snapshotThemes.length ? snapshotThemes.map((item) => {
    const sessions = new Set(item.evidence.map((source) => source.session_id).filter(Boolean));
    const moments = new Set(item.evidence.map((source) => source.transcript_segment_id ?? source.clinical_note_version_id).filter(Boolean));
    return { key: item.id, label: insightLabel(item.content), sessionCount: sessions.size, momentCount: moments.size };
  }) : [];
  const themeCount = themeMetrics.length;
  const openThreadCount = currentItems.filter((item) => item.kind === "open_thread").length;
  const awaitingReview = currentItems.filter((item) => item.review_state === "draft").length;
  const acceptedSessions = Array.from(acceptedJourney.reduce((sessions, entry) => {
    const acceptedAt = Number.isFinite(Date.parse(entry.created_at)) ? Date.parse(entry.created_at) : 0;
    sessions.set(entry.session_id, Math.max(sessions.get(entry.session_id) ?? 0, acceptedAt));
    return sessions;
  }, new Map<string, number>()).entries()).sort((left, right) => right[1] - left[1]);
  const latestAcceptedSessionId = acceptedSessions[0]?.[0];
  const acceptedSincePreviousSession = latestAcceptedSessionId ? acceptedJourney.filter((entry) => entry.session_id === latestAcceptedSessionId).length : 0;
  const acceptedEvidenceDetail = acceptedSessions.length > 1
    ? `${acceptedSincePreviousSession} added since previous session.`
    : `${acceptedSincePreviousSession} captured in the current record.`;
  const insightModules = buildInsightModules(currentItems);
  const hasMetrics = themeCount > 0 || openThreadCount > 0 || awaitingReview > 0 || acceptedJourney.length > 0;
  const overview = snapshot ? savedContentText(snapshot.content) : acceptedJourney.length ? "Therapist-accepted evidence is available for future synthesis. Cross-session trajectory and recurring-theme cards will appear only when they have evidence from at least two sessions." : "No source-linked session material is available yet.";
  const overviewDetails = snapshot ? <>
    <p className="text-[15px] leading-7 text-stone-700">{overview}</p>
    <p className="mt-4 text-xs leading-5 text-stone-500">Workspace {snapshot.status} · version {snapshot.version} · generated by {snapshot.generator_name}. Review the cited evidence before relying on generated observations.</p>
  </> : <p className="text-[15px] leading-7 text-stone-700">{overview}</p>;

  return <section className="space-y-4 text-left" aria-label="Clinical insights workspace">
    <header className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
      <h2 className="text-2xl font-semibold tracking-tight text-stone-900">Clinical Overview</h2>
      <InsightsFreshness status={refreshStatus} snapshot={snapshot} />
    </header>
    <section aria-label="Clinical overview content" className="rounded-2xl border border-stone-300 bg-white p-4 shadow-sm">
      {overviewDetails}
    </section>

    {hasMetrics ? <section className="rounded-2xl border border-stone-300 bg-white p-4 shadow-sm" aria-label="At-a-glance insight metrics">
      <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
        {themeCount > 0 ? <StatCard value={themeCount} label="Themes in view" detail="Themes supported across sessions." /> : null}
        {openThreadCount > 0 ? <StatCard value={openThreadCount} label="Open threads" detail="Items that may need follow-up." /> : null}
        {awaitingReview > 0 ? <StatCard value={awaitingReview} label="Awaiting review" detail="Proposals requiring therapist judgment." /> : null}
        {acceptedJourney.length > 0 ? <StatCard value={acceptedJourney.length} label="Accepted evidence" detail={acceptedEvidenceDetail} /> : null}
      </div>
      {themeMetrics.length ? <ThemeRecurrence themes={themeMetrics} /> : null}
      <p className="mt-3 text-xs leading-5 text-stone-500">These counts organize the available record; they are not clinical scores or conclusions.</p>
    </section> : null}

    {insightModules.length ? <section aria-label="Clinical synthesis sections">
      <div className="grid gap-4">{insightModules.map((module) => <InsightGroup key={module.kind} module={module} onViewEvidence={onViewEvidence} />)}</div>
    </section> : null}
  </section>;
}

export function ClientInsights({ onViewEvidence, recordContext }: Props) {
  const [snapshot, setSnapshot] = useState<PersistedInsightSnapshot | null>(null);
  const [entries, setEntries] = useState<ClientJourneyEntry[]>([]);
  const [refreshStatus, setRefreshStatus] = useState<InsightsRefreshStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadWorkspace = useCallback(async () => {
    if (!recordContext) return null;
    const snapshotRequest = api.getLatestInsightSnapshot(recordContext.organizationId, recordContext.clientId)
      .catch((reason: unknown) => {
        if (reason instanceof ApiError && reason.status === 404) return null;
        throw reason;
      });
    const journeyRequest = api.getClientJourney(recordContext.organizationId, recordContext.clientId)
      .catch((reason: unknown) => {
        throw new Error(`Evidence could not be loaded: ${reason instanceof Error ? reason.message : "Unknown error"}`);
      });
    const statusRequest = api.getInsightsRefreshStatus(recordContext.organizationId, recordContext.clientId)
      .catch((reason: unknown) => {
        throw new Error(`Freshness could not be loaded: ${reason instanceof Error ? reason.message : "Unknown error"}`);
      });
    const [nextSnapshot, journey, nextStatus] = await Promise.all([
      snapshotRequest,
      journeyRequest,
      statusRequest,
    ]);
    return { nextSnapshot, journey, nextStatus };
  }, [recordContext]);

  useEffect(() => {
    if (!recordContext) return;
    let cancelled = false;
    void loadWorkspace()
      .then((result) => {
        if (!cancelled && result) {
          setSnapshot(result.nextSnapshot);
          setEntries(result.journey.entries);
          setRefreshStatus(result.nextStatus);
          setError(null);
        }
      })
      .catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load the clinical insights workspace."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [loadWorkspace, recordContext]);

  useEffect(() => {
    if (!recordContext || loading) return;
    let cancelled = false;
    const interval = window.setInterval(() => {
      void loadWorkspace().then((result) => {
        if (cancelled || !result) return;
        const publishedId = result.nextStatus.published_insight_snapshot_id;
        if (publishedId && result.nextSnapshot?.id !== publishedId) return;
        setSnapshot(result.nextSnapshot);
        setEntries(result.journey.entries);
        setRefreshStatus(result.nextStatus);
        setError(null);
      }).catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not refresh the clinical insights workspace.");
      });
    }, refreshStatus?.status === "pending" || refreshStatus?.status === "running" ? 4_000 : 30_000);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [loadWorkspace, loading, recordContext, refreshStatus?.status]);

  if (!recordContext) return <section className="rounded-2xl border border-stone-300 bg-white p-5 text-left shadow-sm"><h2 className="text-lg font-semibold text-stone-900">Insights</h2><p className="mt-3 text-sm text-stone-600">Open Insights from an authorized client workspace.</p></section>;
  if (error) return <section className="rounded-2xl border border-stone-300 bg-white p-5 text-left shadow-sm"><h2 className="text-lg font-semibold text-stone-900">Insights</h2><p className="mt-3 text-sm text-red-700">{error}</p></section>;
  if (loading) return <InsightsLoadingSkeleton />;
  return <InsightsWorkspace snapshot={snapshot} entries={entries} refreshStatus={refreshStatus} onViewEvidence={onViewEvidence} />;
}
