"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { TranscriptLibrary } from "@/components/session-review/transcript-library";
import { SessionCardCarousel, nextScheduledSession } from "@/components/session-review/session-card-carousel";
import { TranscriptViewer } from "@/components/session-review/transcript-viewer";
import { ScheduledSessionLayout } from "@/components/session-review/scheduled-session-layout";
import { CompletedSessionLayout } from "@/components/session-review/completed-session-layout";
import { ClientCareSettings } from "@/components/client-care-settings";
import { ClientInsights } from "@/components/client-insights";
import { CareRelationshipHeader, type CareProfile } from "@/components/care-relationship-header";
import { LoadingSpinner } from "@/components/loading-spinner";
import { api } from "@/lib/api";
import type { BriefEvidence, Transcript, TranscriptListItem } from "@/lib/types";
import { readSessionView, subscribeToSessionView } from "@/lib/workspace-preferences";

const pause = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

export function SessionWorkspace({ profile }: { profile: CareProfile }) {
  const [transcripts, setTranscripts] = useState<TranscriptListItem[]>([]); const [transcript, setTranscript] = useState<Transcript | null>(null); const [activeId, setActiveId] = useState<string | null>(null); const [activeSessionType, setActiveSessionType] = useState<"scheduled" | "completed">("scheduled"); const [activeSegment, setActiveSegment] = useState(-1); const [isPlaying, setIsPlaying] = useState(false); const [isRecording, setIsRecording] = useState(false); const [isBusy, setIsBusy] = useState(false); const [, setStatus] = useState("Press record to begin."); const [libraryError, setLibraryError] = useState<string | null>(null); const [activeClientView, setActiveClientView] = useState<"clinical-workspace" | "care-settings" | "insights">("clinical-workspace"); const [workspaceVisit, setWorkspaceVisit] = useState(0);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const uploadInFlight = useRef(false);
  const [libraryLoading, setLibraryLoading] = useState(true);
  const [transcriptLoading, setTranscriptLoading] = useState(false);
  const [transcriptError, setTranscriptError] = useState<string | null>(null);
  const transcriptRequest = useRef(0);
  const recorder = useRef<MediaRecorder | null>(null); const stream = useRef<MediaStream | null>(null); const chunks = useRef<Blob[]>([]); const audio = useRef<HTMLAudioElement | null>(null);
  const sessionView = useSyncExternalStore(subscribeToSessionView, readSessionView, () => "cards");
  const loadLibrary = useCallback(async () => { try { setLibraryError(null); setTranscripts(await api.listTranscripts()); } catch (error) { setLibraryError(error instanceof Error ? error.message : "Could not load saved transcripts."); } finally { setLibraryLoading(false); } }, []);
  useEffect(() => { void Promise.resolve().then(loadLibrary); }, [loadLibrary]); useEffect(() => () => stream.current?.getTracks().forEach((track) => track.stop()), []);
  const openTranscript = async (id: string, message = "Viewing saved transcript.", evidenceSegmentIndex?: number) => {
    const request = ++transcriptRequest.current;
    setActiveId(id); setActiveSessionType("completed"); setActiveSegment(evidenceSegmentIndex ?? -1);
    setTranscript(null); setTranscriptLoading(true); setTranscriptError(null);
    try { const data = await api.getTranscript(id); if (request === transcriptRequest.current) { setTranscript(data); setStatus(message); } }
    catch (error) { if (request === transcriptRequest.current) setTranscriptError(error instanceof Error ? error.message : "Could not open transcript."); }
    finally { if (request === transcriptRequest.current) setTranscriptLoading(false); }
  };
  const selectScheduled = (id: string | null) => { transcriptRequest.current++; audio.current?.pause(); setActiveId(id); setTranscript(null); setActiveSegment(-1); setTranscriptLoading(false); setActiveSessionType("scheduled"); };
  const openClinicalWorkspace = () => { selectScheduled(nextScheduledSession(transcripts)?.id ?? null); setActiveClientView("clinical-workspace"); setWorkspaceVisit(visit => visit + 1); };
  const waitForCompletion = async (id: string) => { while (true) { await pause(5000); const job = await api.getJobStatus(id); if (job.status === "COMPLETED") return; if (job.status === "FAILED") throw new Error(job.detail || "HealthScribe could not complete the recording."); setStatus(`HealthScribe status: ${job.status}…`); } };
  const sendRecording = async () => { stream.current?.getTracks().forEach((track) => track.stop()); setIsRecording(false); setIsBusy(true); setStatus("Transcribing…"); try { const blob = new Blob(chunks.current, { type: recorder.current?.mimeType || "audio/webm" }); const job = await api.uploadRecording(blob); setStatus("HealthScribe is processing the recording…"); await waitForCompletion(job.id); await openTranscript(job.id, "Done."); await loadLibrary(); } catch (error) { setStatus(error instanceof Error ? `Could not transcribe: ${error.message}` : "Could not transcribe the recording."); } finally { setIsBusy(false); } };
  const uploadAudio = async (file: File) => {
    if (uploadInFlight.current || isBusy || isRecording) return;
    setUploadError(null);
    setUploadStatus(null);
    if (!/\.(wav|mp3|m4a|mp4|flac|ogg|webm|amr)$/i.test(file.name)) { setUploadError("Choose a WAV, MP3, M4A, MP4, FLAC, Ogg, WebM, or AMR audio file."); return; }
    if (!file.size || file.size > 100 * 1024 * 1024) { setUploadError("Choose a non-empty audio file up to 100 MB."); return; }
    uploadInFlight.current = true;
    setIsBusy(true);
    setUploadStatus("Uploading audio…");
    try {
      const job = await api.uploadRecording(file);
      setUploadStatus("HealthScribe is processing your audio…");
      await waitForCompletion(job.id);
      await loadLibrary();
      await openTranscript(job.id);
      setWorkspaceVisit(visit => visit + 1);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Could not process the audio recording.");
    } finally {
      uploadInFlight.current = false;
      setIsBusy(false);
      setUploadStatus(null);
    }
  };
  const toggleRecording = async () => { if (recorder.current?.state === "recording") { recorder.current.stop(); return; } try { stream.current = await navigator.mediaDevices.getUserMedia({ audio: true }); chunks.current = []; const nextRecorder = new MediaRecorder(stream.current); recorder.current = nextRecorder; nextRecorder.addEventListener("dataavailable", (event) => chunks.current.push(event.data)); nextRecorder.addEventListener("stop", () => void sendRecording(), { once: true }); nextRecorder.start(); setIsRecording(true); setStatus("Recording… press Stop when finished."); } catch (error) { setStatus(error instanceof Error ? `Microphone unavailable: ${error.message}` : "Microphone unavailable."); } };
  const playSegment = (index: number) => { const player = audio.current; if (!player || !transcript?.recording_url) { setStatus("Audio is not available for this transcript."); return; } if (index === activeSegment) { if (player.paused) void player.play().catch(() => setStatus("Audio playback could not start.")); else player.pause(); return; } player.currentTime = transcript.segments[index].start; setActiveSegment(index); void player.play().catch(() => setStatus("Audio playback could not start.")); };
  const transcriptViewer = transcriptLoading ? <LoadingSpinner label="Loading transcript…" /> : transcriptError ? <p role="alert" className="p-5 text-sm text-red-700">{transcriptError}</p> : <TranscriptViewer key={activeId} transcript={transcript} activeSegment={activeSegment} isPlaying={isPlaying} onPlaySegment={playSegment} onAudioTimeUpdate={(event) => setActiveSegment(transcript?.segments.findIndex((segment) => event.currentTarget.currentTime >= segment.start && event.currentTarget.currentTime < segment.end) ?? -1)} onAudioPlay={() => setIsPlaying(true)} onAudioPause={() => setIsPlaying(false)} onAudioEnded={() => { setIsPlaying(false); setActiveSegment(-1); }} />;
  const activeSessionLabel = transcripts.find((savedTranscript) => savedTranscript.id === activeId)?.label || activeId || "Session";
  const activeSessionLayout = activeSessionType === "scheduled" ? <ScheduledSessionLayout isRecording={isRecording} isBusy={isBusy} onToggleRecording={() => void toggleRecording()} onUploadAudio={file => void uploadAudio(file)} onViewEvidence={(source: BriefEvidence) => void openTranscript(source.session_id, `Reviewing cited evidence from ${source.session_label}.`, source.segment_index)} /> : <CompletedSessionLayout sessionId={activeSessionLabel}>{transcriptViewer}</CompletedSessionLayout>;


  return (
    <main className="mx-auto w-[min(92vw,1080px)] py-8 text-center">
      <div className="mb-4 text-left"><Link href="/clients" prefetch={false} className="inline-flex cursor-grab items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing">Back to client list</Link></div>
      <CareRelationshipHeader profile={profile} activeAction={activeClientView} actions={[
        { id: "clinical-workspace", label: "Clinical workspace", icon: "workspace", onSelect: openClinicalWorkspace },
        { id: "billing", label: "Billing", icon: "billing", comingSoon: true },
        { id: "reports", label: "Reports", icon: "reports", comingSoon: true },
        { id: "insights", label: "Insights", icon: "insights", onSelect: () => setActiveClientView("insights") },
        { id: "care-settings", label: "Client care settings", icon: "settings", onSelect: () => setActiveClientView("care-settings") },
        { id: "chat", label: "Chat", icon: "chat", comingSoon: true },
      ]} />
      {uploadStatus && <LoadingSpinner label={uploadStatus} />}
      {uploadError && <p role="alert" className="mb-4 rounded-xl border border-stone-200 bg-white p-4 text-left text-sm text-red-700">{uploadError}</p>}
      <div id="clinical-workspace" className="scroll-mt-6">
        {activeClientView === "insights" ? <ClientInsights onViewEvidence={(source) => { setActiveClientView("clinical-workspace"); void openTranscript(source.session_id, `Reviewing cited evidence from ${source.session_label}.`, source.segment_index); }} /> : activeClientView === "care-settings" ? <ClientCareSettings onReturnToWorkspace={openClinicalWorkspace} />  : libraryLoading ? <LoadingSpinner label="Loading sessions…" /> : sessionView === "cards" ? <><SessionCardCarousel key={workspaceVisit} transcripts={transcripts} activeId={activeId ?? nextScheduledSession(transcripts)?.id ?? null} error={libraryError} onOpen={(id) => void openTranscript(id)} onSelectScheduled={session => selectScheduled(session.id)} onEditSchedule={() => setActiveClientView("care-settings")} /><div className="mt-6 text-left" ref={(node) => { audio.current = node?.querySelector("audio") ?? null; }}>{activeSessionLayout}</div></> : <div className="mt-6 grid items-start gap-6 text-left md:grid-cols-[minmax(380px,440px)_minmax(0,1fr)]"><TranscriptLibrary transcripts={transcripts} activeId={activeId} error={libraryError} onOpen={(id) => void openTranscript(id)} /><div className="min-w-0" ref={(node) => { audio.current = node?.querySelector("audio") ?? null; }}>{activeSessionLayout}</div></div>}
      </div>
    </main>
  );
}
