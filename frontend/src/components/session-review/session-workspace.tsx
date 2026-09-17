"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { TranscriptLibrary } from "@/components/session-review/transcript-library";
import { SessionCardCarousel } from "@/components/session-review/session-card-carousel";
import { TranscriptViewer } from "@/components/session-review/transcript-viewer";
import { ScheduledSessionLayout } from "@/components/session-review/scheduled-session-layout";
import { CompletedSessionLayout } from "@/components/session-review/completed-session-layout";
import { ClientCareSettings } from "@/components/client-care-settings";
import { ClientInsights } from "@/components/client-insights";
import { api } from "@/lib/api";
import type { BriefEvidence, Transcript, TranscriptListItem } from "@/lib/types";
import { readSessionView, subscribeToSessionView } from "@/lib/workspace-preferences";

const pause = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

function MailIcon() {
  return <svg aria-hidden="true" className="size-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="m3.75 6.75 7.5 5.25a1.3 1.3 0 0 0 1.5 0l7.5-5.25M5.25 4.5h13.5c.83 0 1.5.67 1.5 1.5v12c0 .83-.67 1.5-1.5 1.5H5.25c-.83 0-1.5-.67-1.5-1.5V6c0-.83.67-1.5 1.5-1.5Z" /></svg>;
}

function PhoneIcon() {
  return <svg aria-hidden="true" className="size-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M6.62 3.75h2.2c.5 0 .94.33 1.08.8l.88 3.07a1.13 1.13 0 0 1-.52 1.29L8.7 9.8a12.04 12.04 0 0 0 5.5 5.5l.9-1.55a1.13 1.13 0 0 1 1.29-.52l3.07.88c.47.14.8.58.8 1.08v2.2c0 .62-.5 1.13-1.13 1.13C10.55 18.52 5.48 13.45 5.48 4.88c0-.62.5-1.13 1.13-1.13Z" /></svg>;
}

function ChatIcon() {
  return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M7.5 18.75 3.75 20.25l1.5-3.75a7.5 7.5 0 1 1 2.25 2.25Z" /><path strokeLinecap="round" d="M8.25 12h.01m3.74 0H12m3.74 0h.01" /></svg>;
}

function WorkspaceIcon() {
  return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 5.25c0-.83.67-1.5 1.5-1.5h12c.83 0 1.5.67 1.5 1.5v13.5c0 .83-.67 1.5-1.5 1.5H6c-.83 0-1.5-.67-1.5-1.5V5.25ZM8.25 8.25h7.5m-7.5 3h7.5m-7.5 3h4.5" /></svg>;
}

function BillingIcon() {
  return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3.75h10.5c.83 0 1.5.67 1.5 1.5v13.5c0 .83-.67 1.5-1.5 1.5H6.75c-.83 0-1.5-.67-1.5-1.5V5.25c0-.83.67-1.5 1.5-1.5ZM8.25 8.25h7.5m-7.5 3h7.5m-7.5 3h3" /></svg>;
}

function ReportsIcon() {
  return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5V10.88c0-.62.5-1.13 1.13-1.13h1.74c.62 0 1.13.5 1.13 1.13v8.62m0 0h3V5.63c0-.62.5-1.13 1.13-1.13h1.74c.62 0 1.13.5 1.13 1.13V19.5m0 0h3v-5.62c0-.62.5-1.13 1.13-1.13h.24c.62 0 1.13.5 1.13 1.13v5.62M3 19.5h18" /></svg>;
}

function InsightsIcon() {
  return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5V10.88c0-.62.5-1.13 1.13-1.13h1.74c.62 0 1.13.5 1.13 1.13v8.62m0 0h3V5.63c0-.62.5-1.13 1.13-1.13h1.74c.62 0 1.13.5 1.13 1.13V19.5m0 0h3v-5.62c0-.62.5-1.13 1.13-1.13h.24c.62 0 1.13.5 1.13 1.13v5.62M3 19.5h18" /><path strokeLinecap="round" strokeLinejoin="round" d="m8.25 13.5 2.25-2.25 1.5 1.5 3.75-3.75" /></svg>;
}

function CareSettingsIcon() {
  return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M10.3 4.32a1.65 1.65 0 0 1 3.4 0l.16.9a1.65 1.65 0 0 0 2.48 1.17l.78-.47a1.65 1.65 0 0 1 2.4 2.4l-.47.78a1.65 1.65 0 0 0 1.17 2.48l.9.16a1.65 1.65 0 0 1 0 3.4l-.9.16a1.65 1.65 0 0 0-1.17 2.48l.47.78a1.65 1.65 0 0 1-2.4 2.4l-.78-.47a1.65 1.65 0 0 0-2.48 1.17l-.16.9a1.65 1.65 0 0 1-3.4 0l-.16-.9a1.65 1.65 0 0 0-2.48-1.17l-.78.47a1.65 1.65 0 0 1-2.4-2.4l.47-.78a1.65 1.65 0 0 0-1.17-2.48l-.9-.16a1.65 1.65 0 0 1 0-3.4l.9-.16A1.65 1.65 0 0 0 5.2 8.66l-.47-.78a1.65 1.65 0 0 1 2.4-2.4l.78.47a1.65 1.65 0 0 0 2.48-1.17l.16-.9Z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>;
}

export function SessionWorkspace() {
  const [transcripts, setTranscripts] = useState<TranscriptListItem[]>([]); const [transcript, setTranscript] = useState<Transcript | null>(null); const [activeId, setActiveId] = useState<string | null>(null); const [activeSessionType, setActiveSessionType] = useState<"scheduled" | "completed">("scheduled"); const [activeSegment, setActiveSegment] = useState(-1); const [isPlaying, setIsPlaying] = useState(false); const [isRecording, setIsRecording] = useState(false); const [isBusy, setIsBusy] = useState(false); const [, setStatus] = useState("Press record to begin."); const [libraryError, setLibraryError] = useState<string | null>(null); const [activeClientView, setActiveClientView] = useState<"clinical-workspace" | "care-settings" | "insights">("clinical-workspace"); const [workspaceVisit, setWorkspaceVisit] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null); const stream = useRef<MediaStream | null>(null); const chunks = useRef<Blob[]>([]); const audio = useRef<HTMLAudioElement | null>(null);
  const sessionView = useSyncExternalStore(subscribeToSessionView, readSessionView, () => "cards");
  const loadLibrary = useCallback(async () => { try { setLibraryError(null); setTranscripts(await api.listTranscripts()); } catch (error) { setLibraryError(error instanceof Error ? error.message : "Could not load saved transcripts."); } }, []);
  useEffect(() => { void loadLibrary(); }, [loadLibrary]); useEffect(() => () => stream.current?.getTracks().forEach((track) => track.stop()), []);
  const openTranscript = async (id: string, message = "Viewing saved transcript.", evidenceSegmentIndex?: number) => { setActiveId(id); setActiveSessionType("completed"); setActiveSegment(evidenceSegmentIndex ?? -1); try { const data = await api.getTranscript(id); setTranscript(data); setStatus(message); } catch (error) { setStatus(error instanceof Error ? error.message : "Could not open transcript."); } };
  const openClinicalWorkspace = () => { const mostRecentTranscript = transcripts.reduce<TranscriptListItem | null>((latest, candidate) => !latest || new Date(candidate.created_at).getTime() > new Date(latest.created_at).getTime() ? candidate : latest, null); setActiveClientView("clinical-workspace"); setWorkspaceVisit((visit) => visit + 1); if (mostRecentTranscript) void openTranscript(mostRecentTranscript.id, "Viewing the most recent completed session."); };
  const waitForCompletion = async (id: string) => { while (true) { await pause(5000); const job = await api.getJobStatus(id); if (job.status === "COMPLETED") return; if (job.status === "FAILED") throw new Error(job.detail || "HealthScribe could not complete the recording."); setStatus(`HealthScribe status: ${job.status}…`); } };
  const sendRecording = async () => { stream.current?.getTracks().forEach((track) => track.stop()); setIsRecording(false); setIsBusy(true); setStatus("Transcribing…"); try { const blob = new Blob(chunks.current, { type: recorder.current?.mimeType || "audio/webm" }); const job = await api.uploadRecording(blob); setStatus("HealthScribe is processing the recording…"); await waitForCompletion(job.id); await openTranscript(job.id, "Done."); await loadLibrary(); } catch (error) { setStatus(error instanceof Error ? `Could not transcribe: ${error.message}` : "Could not transcribe the recording."); } finally { setIsBusy(false); } };
  const toggleRecording = async () => { if (recorder.current?.state === "recording") { recorder.current.stop(); return; } try { stream.current = await navigator.mediaDevices.getUserMedia({ audio: true }); chunks.current = []; const nextRecorder = new MediaRecorder(stream.current); recorder.current = nextRecorder; nextRecorder.addEventListener("dataavailable", (event) => chunks.current.push(event.data)); nextRecorder.addEventListener("stop", () => void sendRecording(), { once: true }); nextRecorder.start(); setIsRecording(true); setStatus("Recording… press Stop when finished."); } catch (error) { setStatus(error instanceof Error ? `Microphone unavailable: ${error.message}` : "Microphone unavailable."); } };
  const playSegment = (index: number) => { const player = audio.current; if (!player || !transcript?.recording_url) { setStatus("Audio is not available for this transcript."); return; } if (index === activeSegment) { if (player.paused) void player.play().catch(() => setStatus("Audio playback could not start.")); else player.pause(); return; } player.currentTime = transcript.segments[index].start; setActiveSegment(index); void player.play().catch(() => setStatus("Audio playback could not start.")); };
  const transcriptViewer = <TranscriptViewer transcript={transcript} activeSegment={activeSegment} isPlaying={isPlaying} onPlaySegment={playSegment} onAudioTimeUpdate={(event) => setActiveSegment(transcript?.segments.findIndex((segment) => event.currentTarget.currentTime >= segment.start && event.currentTarget.currentTime < segment.end) ?? -1)} onAudioPlay={() => setIsPlaying(true)} onAudioPause={() => setIsPlaying(false)} onAudioEnded={() => { setIsPlaying(false); setActiveSegment(-1); }} />;
  const activeSessionLabel = transcripts.find((savedTranscript) => savedTranscript.id === activeId)?.label || activeId || "Session";
  const activeSessionLayout = activeSessionType === "scheduled" ? <ScheduledSessionLayout isRecording={isRecording} isBusy={isBusy} onToggleRecording={() => void toggleRecording()} onViewEvidence={(source: BriefEvidence) => void openTranscript(source.session_id, `Reviewing cited evidence from ${source.session_label}.`, source.segment_index)} /> : <CompletedSessionLayout sessionId={activeSessionLabel}>{transcriptViewer}</CompletedSessionLayout>;
  const clientNavItemClass = "inline-flex min-w-fit flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm";

  return (
    <main className="mx-auto w-[min(92vw,1080px)] py-8 text-center">
      <section className="mb-6 overflow-hidden rounded-2xl border border-stone-200 bg-stone-50 text-left shadow-sm">
        <div className="p-5"><div className="flex min-w-0 items-center gap-4"><div className="grid size-14 shrink-0 place-items-center rounded-full bg-emerald-800 text-lg font-semibold text-white" aria-hidden="true">ES</div><div className="min-w-0"><p className="text-sm font-medium text-emerald-800">Client</p><h1 className="mt-0.5 truncate text-xl font-semibold tracking-tight text-stone-900">Elena Sadić</h1><div className="mt-2 flex flex-col gap-1 text-sm text-stone-600 sm:flex-row sm:gap-4"><span className="inline-flex items-center gap-1.5"><MailIcon />elena.sadic@example.com</span><span className="inline-flex items-center gap-1.5"><PhoneIcon />(555) 014-2048</span></div></div></div></div>
        <nav className="flex gap-1 overflow-x-auto border-t border-stone-200 bg-white px-3 py-2" aria-label="Elena Sadić client navigation">
          <button type="button" onClick={openClinicalWorkspace} className={`${clientNavItemClass} cursor-grab font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing ${activeClientView === "clinical-workspace" ? "bg-emerald-50 text-emerald-900" : "text-stone-600 hover:bg-stone-100"}`} aria-current={activeClientView === "clinical-workspace" ? "page" : undefined}><WorkspaceIcon />Clinical workspace</button>
          <button type="button" aria-disabled="true" title="Client billing is coming soon" className={`${clientNavItemClass} cursor-not-allowed font-medium text-stone-500`}><BillingIcon />Billing <span className="rounded-full bg-stone-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-stone-500">Soon</span></button>
          <button type="button" aria-disabled="true" title="Client reports are coming soon" className={`${clientNavItemClass} cursor-not-allowed font-medium text-stone-500`}><ReportsIcon />Reports <span className="rounded-full bg-stone-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-stone-500">Soon</span></button>
          <button type="button" onClick={() => setActiveClientView("insights")} className={`${clientNavItemClass} cursor-grab font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing ${activeClientView === "insights" ? "bg-emerald-50 text-emerald-900" : "text-stone-600 hover:bg-stone-100"}`} aria-current={activeClientView === "insights" ? "page" : undefined}><InsightsIcon />Insights</button>
          <button type="button" onClick={() => setActiveClientView("care-settings")} className={`${clientNavItemClass} cursor-grab font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing ${activeClientView === "care-settings" ? "bg-emerald-50 text-emerald-900" : "text-stone-600 hover:bg-stone-100"}`} aria-current={activeClientView === "care-settings" ? "page" : undefined}><CareSettingsIcon />Client care settings</button>
          <button type="button" aria-disabled="true" title="Client chat is coming soon" className={`${clientNavItemClass} cursor-not-allowed font-medium text-stone-500`}><ChatIcon />Chat <span className="rounded-full bg-stone-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-stone-500">Soon</span></button>
        </nav>
      </section>
      <div id="clinical-workspace" className="scroll-mt-6">
        {activeClientView === "insights" ? <ClientInsights onViewEvidence={(source) => { setActiveClientView("clinical-workspace"); void openTranscript(source.session_id, `Reviewing cited evidence from ${source.session_label}.`, source.segment_index); }} /> : activeClientView === "care-settings" ? <ClientCareSettings onReturnToWorkspace={openClinicalWorkspace} /> : sessionView === "cards" ? <><SessionCardCarousel key={workspaceVisit} transcripts={transcripts} activeId={activeId} error={libraryError} onOpen={(id) => void openTranscript(id)} onSelectScheduled={() => { setActiveId(null); setTranscript(null); setActiveSessionType("scheduled"); }} onEditSchedule={() => setActiveClientView("care-settings")} /><div className="mt-6 text-left" ref={(node) => { audio.current = node?.querySelector("audio") ?? null; }}>{activeSessionLayout}</div></> : <div className="mt-6 grid items-start gap-6 text-left md:grid-cols-[minmax(380px,440px)_minmax(0,1fr)]"><TranscriptLibrary transcripts={transcripts} activeId={activeId} error={libraryError} onOpen={(id) => void openTranscript(id)} /><div className="min-w-0" ref={(node) => { audio.current = node?.querySelector("audio") ?? null; }}>{activeSessionLayout}</div></div>}
      </div>
    </main>
  );
}
