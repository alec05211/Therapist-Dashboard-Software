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

type BriefItem = PreSessionBrief["sections"][number]["items"][number];

function EvidenceLink({ item, onViewEvidence }: { item: BriefItem; onViewEvidence: (source: BriefEvidence) => void }) {
  const primarySource = item.sources[0];
  if (!primarySource) return <>{item.text}</>;
  const sessionNames = item.sources.map((source) => source.session_label.replace("Synthetic · Elena Sadić · ", "")).join(", ");

  return <button type="button" onClick={() => onViewEvidence(primarySource)} className="cursor-grab text-left decoration-stone-400 decoration-1 underline underline-offset-4 transition duration-200 ease-out hover:text-emerald-950 hover:decoration-emerald-700 active:cursor-grabbing focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-700" aria-label={`Open cited transcript evidence from ${sessionNames}`} title={`Open cited transcript evidence from ${sessionNames}`}>{item.text}</button>;
}

function BriefNarrative({ brief, onViewEvidence }: { brief: PreSessionBrief; onViewEvidence: (source: BriefEvidence) => void }) {
  const latestSession = brief.sections.find((section) => section.title === "Since last session")?.items ?? [];
  const trajectory = brief.sections.find((section) => section.title === "Important trajectory")?.items ?? [];
  const openLoops = brief.sections.find((section) => section.title === "Open loops")?.items ?? [];
  const remainingContext = brief.sections
    .filter((section) => !["Since last session", "Important trajectory", "Open loops"].includes(section.title))
    .flatMap((section) => section.items);
  const narrativeItems = [...latestSession, ...trajectory, ...remainingContext];

  return <>
    <p className="mt-5 max-w-3xl text-[15px] leading-7 text-stone-700">
      {latestSession.length > 0 ? <>The last session returned to <EvidenceLink item={latestSession[0]} onViewEvidence={onViewEvidence} />. </> : null}
      {latestSession.slice(1).map((item) => <span key={item.text}><EvidenceLink item={item} onViewEvidence={onViewEvidence} />. </span>)}
      {trajectory.length > 0 ? <>It also offers a possible trajectory to consider: <EvidenceLink item={trajectory[0]} onViewEvidence={onViewEvidence} />. </> : null}
      {trajectory.slice(1).map((item) => <span key={item.text}><EvidenceLink item={item} onViewEvidence={onViewEvidence} />. </span>)}
      {remainingContext.map((item) => <span key={item.text}><EvidenceLink item={item} onViewEvidence={onViewEvidence} />. </span>)}
      {narrativeItems.length === 0 ? "No cited context is available for this upcoming session." : null}
    </p>

    {openLoops.length > 0 ? <div className="mt-5 max-w-3xl border-l-2 border-stone-200 pl-4">
      <p className="text-sm leading-6 text-stone-600">It may be useful to return to:</p>
      <ul className="mt-2 grid gap-2 pl-4 text-[15px] leading-7 text-stone-700 marker:text-stone-400">
        {openLoops.map((item) => <li key={item.text}><EvidenceLink item={item} onViewEvidence={onViewEvidence} /></li>)}
      </ul>
    </div> : null}
  </>;
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
    <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm" aria-label="Scheduled session preparation">
      <p className="text-sm font-medium text-emerald-800">Scheduled session</p>
      <h2 className="mt-1 text-lg font-semibold text-stone-900">Prepare for this session</h2>
      <p className="mt-2 text-sm leading-6 text-stone-600">A short orientation from the client’s finalized record.</p>

      <section className="mt-5 border-y border-stone-200 py-4" aria-label="Pre-session brief">
        <div className="flex flex-wrap items-start justify-between gap-x-5 gap-y-2">
          <div>
            <h3 className="text-base font-semibold text-stone-900">Before this session</h3>
            <p className="mt-1 text-xs leading-5 text-stone-600">Underlined text opens the exact cited transcript moment.</p>
          </div>
          <div className="flex items-center gap-3 pt-0.5">
            {brief ? <span className="text-xs font-medium text-emerald-800">{brief.status}</span> : null}
            <button type="button" onClick={() => void generateWithOpenAI()} disabled={isGenerating} className="cursor-grab text-xs font-medium text-emerald-800 underline underline-offset-2 transition hover:text-emerald-950 active:cursor-grabbing disabled:cursor-wait disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">{isGenerating ? "Generating…" : "Refresh draft"}</button>
          </div>
        </div>
        {briefError ? <p className="mt-4 text-sm text-red-700">{briefError}</p> : null}
        {!brief && !briefError ? <p className="mt-4 text-sm text-stone-600">Preparing cited context…</p> : null}
        {brief ? <>
          <BriefNarrative brief={brief} onViewEvidence={onViewEvidence} />
          <p className="mt-4 text-xs leading-5 text-stone-500">{brief.review_note}</p>
        </> : null}
      </section>

      <div className="mt-5"><RecordingControls isRecording={isRecording} isBusy={isBusy} onToggle={onToggleRecording} /></div>
    </section>
  );
}
