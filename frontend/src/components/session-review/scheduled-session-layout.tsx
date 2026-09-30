"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { RecordingControls } from "@/components/session-review/recording-controls";
import { AudioUploadButton } from "@/components/session-review/audio-upload-button";
import { ApiError, api } from "@/lib/api";
import type { BriefEvidence, LongitudinalRecordContext, PreSessionBrief } from "@/lib/types";

type ScheduledSessionLayoutProps = {
  isRecording: boolean;
  isBusy: boolean;
  hasPriorSessions: boolean;
  onReschedule: () => void;
  onToggleRecording: () => void;
  onUploadAudio: (file: File) => void;
  onViewEvidence: (source: BriefEvidence) => void;
  recordContext?: LongitudinalRecordContext;
};

type BriefItem = PreSessionBrief["sections"][number]["items"][number];

function ClaimLink({ phrase, sources, onViewEvidence, fallback = false }: { phrase: string; sources: BriefEvidence[]; onViewEvidence: (source: BriefEvidence) => void; fallback?: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  return <>
    <button type="button" onClick={() => dialog.current?.showModal()} aria-haspopup="dialog" aria-label={`View evidence for ${phrase}`} className={`${fallback ? "ml-1 text-xs font-medium" : "font-bold"} inline cursor-grab rounded-sm text-left text-stone-800 hover:text-emerald-800 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700`}>{fallback ? "Evidence" : phrase}</button>
    {typeof document !== "undefined" && createPortal(<dialog ref={dialog} aria-labelledby={titleId} onClick={event => { if (event.target === event.currentTarget) dialog.current?.close(); }} className="m-auto max-h-[85vh] w-[min(92vw,640px)] overflow-y-auto rounded-2xl border border-stone-300 bg-white p-6 text-left text-stone-800 shadow-xl backdrop:bg-stone-950/50">
      <span className="flex items-start justify-between gap-4"><span id={titleId} className="text-base font-semibold">Supporting context</span><button type="button" onClick={() => dialog.current?.close()} aria-label="Close supporting context" className="cursor-grab rounded-lg px-2 text-xl active:cursor-grabbing focus-visible:outline-2">×</button></span>
      <span className="my-4 block text-base leading-7">{phrase}</span>
      {sources.map(source => <span key={source.evidence_id} className="mt-3 block rounded-xl border border-stone-300 p-4 text-sm leading-6">
        <span className="block font-semibold">{source.session_label}</span>
        {source.quote && <span className="mt-2 block">“{source.quote}”</span>}
        <button type="button" onClick={() => { dialog.current?.close(); onViewEvidence(source); }} className="mt-3 cursor-grab rounded-lg border border-stone-300 px-3 py-1 font-semibold text-emerald-800 hover:bg-stone-100 active:cursor-grabbing">Open transcript evidence</button>
      </span>)}
    </dialog>, document.body)}
  </>;
}

function EvidenceLink({ item, onViewEvidence }: { item: BriefItem; onViewEvidence: (source: BriefEvidence) => void }) {
  const spans = (item.claims ?? []).map(claim => {
    let start = -1;
    for (let i = 0; i <= claim.occurrence; i++) { start = item.text.indexOf(claim.phrase, start + 1); if (start < 0) break; }
    return { ...claim, start, end: start + claim.phrase.length };
  }).sort((a, b) => a.start - b.start);
  const valid = spans.length > 0 && spans.every((span, index) => span.start >= 0 && span.sources.length > 0 && (!index || span.start >= spans[index - 1].end));
  if (!valid) return <>{item.text}{item.sources.length > 0 && <ClaimLink phrase={item.text} sources={item.sources} onViewEvidence={onViewEvidence} fallback />}</>;
  return <>{spans.map((span, index) => <span key={`${span.start}-${span.end}`}>
    {item.text.slice(index ? spans[index - 1].end : 0, span.start)}
    <ClaimLink phrase={span.phrase} sources={span.sources} onViewEvidence={onViewEvidence} />
  </span>)}{item.text.slice(spans[spans.length - 1].end)}</>;
}

function BriefNarrative({ brief, onViewEvidence }: { brief: PreSessionBrief; onViewEvidence: (source: BriefEvidence) => void }) {
  if (brief.status === "NO PRIOR CONTEXT") {
    return <p className="mt-5 text-base leading-8 text-stone-800">No prior context or history. Record or upload the first session to begin.</p>;
  }
  const latestSession = brief.sections.find((section) => section.title === "Since last session")?.items ?? [];
  const trajectory = brief.sections.find((section) => section.title === "Important trajectory")?.items ?? [];
  const openLoops = brief.sections.find((section) => section.title === "Open loops")?.items ?? [];
  const remainingContext = brief.sections
    .filter((section) => !["Since last session", "Important trajectory", "Open loops"].includes(section.title))
    .flatMap((section) => section.items);
  const contextItems = [...latestSession, ...trajectory, ...remainingContext];
  const narrativeItems = contextItems.slice(0, 2);
  const reviewItems = contextItems.slice(2);

  return <>
    <p className="mt-5 text-base leading-8 text-stone-800">
      {narrativeItems.map((item, index) => <span key={index}><EvidenceLink item={item} onViewEvidence={onViewEvidence} />{/[.!?…][”"']?$/.test(item.text.trim()) ? " " : ". "}</span>)}
      {narrativeItems.length === 0 ? openLoops.length ? "Review these follow-ups before the upcoming session." : "No cited context is available for this upcoming session." : null}
    </p>

    {openLoops.length > 0 ? <div className="mt-6 rounded-xl border border-stone-300 bg-stone-50 p-4">
      <h3 className="text-sm font-semibold text-stone-900">Follow up this session</h3>
      <ul className="mt-3 list-disc space-y-3 pl-5 text-base leading-7 text-stone-800 marker:text-current">
        {openLoops.map((item) => <li key={item.text}><EvidenceLink item={item} onViewEvidence={onViewEvidence} /></li>)}
      </ul>
    </div> : null}
    {reviewItems.length > 0 ? <div className="mt-5">
      <h3 className="text-sm font-semibold text-stone-900">Keep in mind</h3>
      <ul className="mt-3 list-disc space-y-3 pl-5 text-[15px] leading-7 text-stone-700 marker:text-stone-500">
        {reviewItems.map((item, index) => <li key={index}><EvidenceLink item={item} onViewEvidence={onViewEvidence} /></li>)}
      </ul>
    </div> : null}
  </>;
}

export function ScheduledSessionLayout({ isRecording, isBusy, hasPriorSessions, onReschedule, onToggleRecording, onUploadAudio, onViewEvidence, recordContext }: ScheduledSessionLayoutProps) {
  const [brief, setBrief] = useState<PreSessionBrief | null>(null);
  const [briefError, setBriefError] = useState<string | null>(null);
  const organizationId = recordContext?.organizationId;
  const clientId = recordContext?.clientId;

  const loadBrief = useCallback(async () => {
    if (!organizationId || !clientId) return { result: { status: "AWAITING CLIENT CONTEXT", review_note: "Open this session from an authorized client workspace.", sections: [] } as PreSessionBrief, source: "empty" as const };
    try {
      const result = await api.getCurrentPreSessionBrief(organizationId, clientId);
      return { result, source: "saved" as const };
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 404) throw error;
      return { result: hasPriorSessions
        ? { status: "AWAITING APPROVED INSIGHTS", review_note: "The brief will draw from therapist-approved client journey entries when available.", sections: [] }
        : { status: "NO PRIOR CONTEXT", review_note: "No earlier sessions are available for this client.", sections: [] } as PreSessionBrief, source: "empty" as const };
    }
  }, [organizationId, clientId, hasPriorSessions]);

  useEffect(() => {
    let cancelled = false;
    void loadBrief()
      .then(({ result }) => { if (!cancelled) setBrief(result); })
      .catch((error: unknown) => { if (!cancelled) setBriefError(error instanceof Error ? error.message : "Could not load the pre-session brief."); });
    return () => { cancelled = true; };
  }, [loadBrief]);

  return (
    <div className="grid gap-4" aria-label="Scheduled session preparation">
      <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-stone-300 bg-white p-5 shadow-sm" aria-labelledby="reschedule-session-heading">
        <h2 id="reschedule-session-heading" className="text-lg font-semibold text-stone-900">Reschedule session</h2>
        <button type="button" onClick={onReschedule} className="cursor-grab rounded-xl border border-stone-300 bg-stone-50 px-4 py-2.5 text-sm font-semibold text-stone-800 transition-colors duration-200 hover:border-stone-400 hover:bg-stone-100 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">
          Reschedule
        </button>
      </section>

      <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm" aria-labelledby="pre-session-brief-heading">
        <h2 id="pre-session-brief-heading" className="text-lg font-semibold text-stone-900">Pre-session brief</h2>
        {briefError ? <p className="mt-4 text-sm text-red-700">{briefError}</p> : null}
        {!brief && !briefError ? <p className="mt-4 text-sm text-stone-600">Preparing cited context…</p> : null}
        {brief ? <>
          <BriefNarrative brief={brief} onViewEvidence={onViewEvidence} />
          <p className="mt-4 text-xs leading-5 text-stone-500">{brief.review_note}</p>
        </> : null}
      </section>

      <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm" aria-labelledby="record-session-heading">
        <h2 id="record-session-heading" className="text-lg font-semibold text-stone-900">Record or upload session</h2>
        <div className="mt-4 flex items-center gap-3"><div className="flex-1"><RecordingControls isRecording={isRecording} isBusy={isBusy} onToggle={onToggleRecording} /></div><AudioUploadButton disabled={isRecording || isBusy} onUpload={onUploadAudio} /></div>
      </section>
    </div>
  );
}
