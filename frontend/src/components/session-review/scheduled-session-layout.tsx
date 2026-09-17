"use client";

import { useEffect, useState } from "react";
import { RecordingControls } from "@/components/session-review/recording-controls";
import { api } from "@/lib/api";
import type { BriefEvidence, PreSessionBrief } from "@/lib/types";

type ScheduledSessionLayoutProps = {
  isRecording: boolean;
  isBusy: boolean;
  onToggleRecording: () => void;
  onViewEvidence: (source: BriefEvidence) => void;
};

function EvidenceCitation({ source, onViewEvidence }: { source: BriefEvidence; onViewEvidence: (source: BriefEvidence) => void }) {
  const [isQuoteVisible, setIsQuoteVisible] = useState(false);
  const sessionLabel = source.session_label.replace("Synthetic · Elena Sadić · ", "");

  return (
    <span className="group/evidence relative mt-1 inline-flex items-center gap-1.5 text-xs">
      <button type="button" onClick={() => onViewEvidence(source)} className="cursor-grab font-medium text-emerald-800 underline underline-offset-2 transition hover:text-emerald-950 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">{sessionLabel}</button>
      <button type="button" onClick={() => setIsQuoteVisible((visible) => !visible)} className="grid size-5 cursor-grab place-items-center rounded-md text-emerald-800 opacity-0 transition-opacity duration-200 ease-out hover:bg-emerald-50 active:cursor-grabbing focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 group-hover/evidence:opacity-100" aria-expanded={isQuoteVisible} aria-label={`${isQuoteVisible ? "Hide" : "View"} cited quote from ${sessionLabel}`}>
        <svg aria-hidden="true" className="size-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.9"><path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6.75H6.75a3 3 0 0 0-3 3v4.5a3 3 0 0 0 3 3h3.75a3 3 0 0 0 3-3v-4.5a3 3 0 0 0-3-3Zm6.75 0H13.5a3 3 0 0 0-3 3v4.5a3 3 0 0 0 3 3h3.75a3 3 0 0 0 3-3v-4.5a3 3 0 0 0-3-3Z" /></svg>
      </button>
      {isQuoteVisible ? <span className="absolute left-0 top-6 z-10 w-72 rounded-lg border border-stone-200 bg-white p-3 text-left leading-5 text-stone-700 shadow-sm">“{source.quote}”</span> : null}
    </span>
  );
}

export function ScheduledSessionLayout({ isRecording, isBusy, onToggleRecording, onViewEvidence }: ScheduledSessionLayoutProps) {
  const [brief, setBrief] = useState<PreSessionBrief | null>(null);
  const [briefError, setBriefError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void api.getDemoPreSessionBrief()
      .then((result) => { if (!cancelled) setBrief(result); })
      .catch((error: unknown) => { if (!cancelled) setBriefError(error instanceof Error ? error.message : "Could not load the pre-session brief."); });
    return () => { cancelled = true; };
  }, []);

  const generateWithOpenAI = async () => {
    setIsGenerating(true);
    setBriefError(null);
    try {
      setBrief(await api.generateDemoPreSessionBrief());
    } catch (error) {
      setBriefError(error instanceof Error ? error.message : "Could not generate the OpenAI demo brief.");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-stone-200" aria-label="Scheduled session preparation">
      <p className="text-sm font-medium text-emerald-800">Scheduled session</p>
      <h2 className="mt-1 text-lg font-semibold text-stone-900">Prepare for this session</h2>
      <p className="mt-2 text-sm leading-6 text-stone-600">A concise, evidence-linked orientation for the upcoming conversation.</p>
      <section className="mt-5 rounded-xl border border-stone-200 bg-stone-50 p-4" aria-label="Pre-session brief">
        <div className="flex flex-wrap items-baseline justify-between gap-2"><h3 className="text-base font-semibold text-stone-900">Pre-session brief</h3><div className="flex items-center gap-3">{brief ? <span className="text-xs font-medium text-emerald-800">{brief.status}</span> : null}<button type="button" onClick={() => void generateWithOpenAI()} disabled={isGenerating} className="cursor-grab text-xs font-medium text-emerald-800 underline underline-offset-2 transition hover:text-emerald-950 active:cursor-grabbing disabled:cursor-wait disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">{isGenerating ? "Generating…" : "Generate with OpenAI"}</button></div></div>
        {briefError ? <p className="mt-3 text-sm text-red-700">{briefError}</p> : null}
        {!brief && !briefError ? <p className="mt-3 text-sm text-stone-600">Preparing cited context…</p> : null}
        {brief ? <><p className="mt-2 text-xs leading-5 text-stone-600">{brief.review_note}</p><div className="mt-4 grid gap-4">{brief.sections.map((section) => <section key={section.title} className="border-t border-stone-200 pt-3 first:border-t-0 first:pt-0"><h4 className="text-sm font-semibold text-stone-900">{section.title}</h4><ul className="mt-2 grid gap-3">{section.items.map((item) => <li key={item.text} className="text-sm leading-6 text-stone-700"><p>{item.text}</p><div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">{item.sources.map((source) => <EvidenceCitation key={`${source.session_id}-${source.segment_index}`} source={source} onViewEvidence={onViewEvidence} />)}</div></li>)}</ul></section>)}</div></> : null}
      </section>
      <div className="mt-5 border-t border-stone-200 pt-5">
        <RecordingControls isRecording={isRecording} isBusy={isBusy} onToggle={onToggleRecording} />
      </div>
    </section>
  );
}
