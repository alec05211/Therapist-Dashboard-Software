"use client";

import { useCallback, useEffect, useState } from "react";
import { RecordingControls } from "@/components/session-review/recording-controls";
import { AudioUploadButton } from "@/components/session-review/audio-upload-button";
import { ApiError, api } from "@/lib/api";
import type { BriefEvidence, LongitudinalRecordContext, PreSessionBrief } from "@/lib/types";

type ScheduledSessionLayoutProps = {
  isRecording: boolean;
  isBusy: boolean;
  onToggleRecording: () => void;
  onUploadAudio: (file: File) => void;
  onViewEvidence: (source: BriefEvidence) => void;
  recordContext?: LongitudinalRecordContext;
};

type BriefItem = PreSessionBrief["sections"][number]["items"][number];

function EvidenceLink({ item, onViewEvidence }: { item: BriefItem; onViewEvidence: (source: BriefEvidence) => void }) {
  const primarySource = item.sources[0];
  if (!primarySource) return <>{item.text}</>;
  const sessionNames = item.sources.map((source) => source.session_label.replace("Synthetic · Elena Sadić · ", "")).join(", ");

  return <>{item.text}<sup className="ml-1 inline-flex gap-1 align-super text-[10px] leading-none">{item.sources.map((source, index) => <button key={source.evidence_id} type="button" onClick={() => onViewEvidence(source)} className="cursor-grab font-medium text-emerald-800 underline underline-offset-2 active:cursor-grabbing focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700" aria-label={`Open cited evidence ${index + 1} from ${source.session_label}`} title={sessionNames}>{item.sources.length === 1 ? "source" : index + 1}</button>)}</sup></>;
}

function BriefNarrative({ brief, onViewEvidence }: { brief: PreSessionBrief; onViewEvidence: (source: BriefEvidence) => void }) {
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

export function ScheduledSessionLayout({ isRecording, isBusy, onToggleRecording, onUploadAudio, onViewEvidence, recordContext }: ScheduledSessionLayoutProps) {
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
      return { result: { status: "AWAITING APPROVED INSIGHTS", review_note: "The brief will draw from therapist-approved client journey entries when available.", sections: [] } as PreSessionBrief, source: "empty" as const };
    }
  }, [organizationId, clientId]);

  useEffect(() => {
    let cancelled = false;
    void loadBrief()
      .then(({ result }) => { if (!cancelled) setBrief(result); })
      .catch((error: unknown) => { if (!cancelled) setBriefError(error instanceof Error ? error.message : "Could not load the pre-session brief."); });
    return () => { cancelled = true; };
  }, [loadBrief]);

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-5 text-left shadow-sm" aria-label="Scheduled session preparation">
      <h2 className="text-lg font-semibold text-stone-900">Prepare for this session</h2>

      <section className="border-b border-stone-200 pb-4" aria-label="Pre-session brief">
        {briefError ? <p className="mt-4 text-sm text-red-700">{briefError}</p> : null}
        {!brief && !briefError ? <p className="mt-4 text-sm text-stone-600">Preparing cited context…</p> : null}
        {brief ? <>
          <BriefNarrative brief={brief} onViewEvidence={onViewEvidence} />
          <p className="mt-4 text-xs leading-5 text-stone-500">{brief.review_note}</p>
        </> : null}
      </section>

      <div className="mt-5 flex items-center gap-3"><div className="flex-1"><RecordingControls isRecording={isRecording} isBusy={isBusy} onToggle={onToggleRecording} /></div><AudioUploadButton disabled={isRecording || isBusy} onUpload={onUploadAudio} /></div>
    </section>
  );
}
