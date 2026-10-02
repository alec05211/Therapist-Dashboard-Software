"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { TranscriptLibrary } from "@/components/session-review/transcript-library";
import { SessionCardCarousel, nextScheduledSession } from "@/components/session-review/session-card-carousel";
import { TranscriptViewer } from "@/components/session-review/transcript-viewer";
import { ScheduledSessionLayout } from "@/components/session-review/scheduled-session-layout";
import { CompletedSessionLayout } from "@/components/session-review/completed-session-layout";
import { ClientCareSettings } from "@/components/client-care-settings";
import { ClientInsights } from "@/components/client-insights";
import { ClientJourney } from "@/components/client-journey";
import { ClientDocuments } from "@/components/client-documents";
import { CareChat } from "@/components/care-chat";
import { CareRelationshipHeader, type CareProfile } from "@/components/care-relationship-header";
import { LoadingSpinner } from "@/components/loading-spinner";
import { api } from "@/lib/api";
import type { Appointment, BriefEvidence, SessionProcessingState, Transcript, TranscriptListItem } from "@/lib/types";
import { readClinicalSession, readSessionView, rememberClinicalSession, subscribeToSessionView } from "@/lib/workspace-preferences";

function processingStateForStatus(status: string): SessionProcessingState {
  switch (status) {
    case "UPLOADING": return { phase: "processing", message: "The server is securing the uploaded recording.", progress: null };
    case "QUEUED": return { phase: "processing", message: "The recording is waiting for transcription to begin.", progress: null };
    case "IN_PROGRESS": return { phase: "processing", message: "The recording is being analyzed and transcribed.", progress: null };
    case "RETRIEVING_RESULTS": return { phase: "processing", message: "The completed session is being retrieved.", progress: null };
    case "PREPARING_TRANSCRIPT": return { phase: "processing", message: "The transcript is being prepared for review.", progress: null };
    case "SAVING_SESSION": return { phase: "processing", message: "The completed session is being saved.", progress: null };
    default: return { phase: "processing", message: "The recording is being processed.", progress: null };
  }
}

export function SessionWorkspace({ profile, initialView = "clinical-workspace" }: {
  profile: CareProfile;
  initialView?: "clinical-workspace" | "chat";
}) {
  const recordContext = useMemo(() => profile.organizationId && profile.clientId
    ? { organizationId: profile.organizationId, clientId: profile.clientId }
    : undefined, [profile.organizationId, profile.clientId]);
  const [newClientSetup, setNewClientSetup] = useState(Boolean(profile.needsSetup));
  const [configuringSessions, setConfiguringSessions] = useState(false);
  const setupAppointments = useMemo<Appointment[]>(() => [1, 8, 15].map((offset, index) => {
    const startsAt = new Date(); startsAt.setDate(startsAt.getDate() + offset); startsAt.setHours(10 + index, 0, 0, 0);
    return { id: `setup-${index}`, organization_id: profile.organizationId || "", client_id: profile.clientId || "", client_name: profile.name, starts_at: startsAt.toISOString(), ends_at: new Date(startsAt.getTime() + 50 * 60_000).toISOString(), status: "scheduled", appointment_type: "recurring", meeting_mode: "in_person" };
  }), [profile.clientId, profile.name, profile.organizationId]);
  const [transcripts, setTranscripts] = useState<TranscriptListItem[]>([]); const [transcript, setTranscript] = useState<Transcript | null>(null); const [activeId, setActiveId] = useState<string | null>(null); const [activeSessionType, setActiveSessionType] = useState<"scheduled" | "completed">("scheduled"); const [activeSegment, setActiveSegment] = useState(-1); const [isPlaying, setIsPlaying] = useState(false); const [isRecording, setIsRecording] = useState(false); const [isBusy, setIsBusy] = useState(false); const [, setStatus] = useState("Press record to begin."); const [libraryError, setLibraryError] = useState<string | null>(null); const [activeClientView, setActiveClientView] = useState<"clinical-workspace" | "documents" | "care-settings" | "insights" | "chat">(initialView); const [workspaceVisit, setWorkspaceVisit] = useState(0);
  const [processingState, setProcessingState] = useState<SessionProcessingState | null>(null);
  const [processingJobId, setProcessingJobId] = useState<string | null>(null);
  const [processingAppointmentId, setProcessingAppointmentId] = useState<string | null>(null);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(!profile.needsSetup);
  const [careSettingsSection, setCareSettingsSection] = useState<"identification" | "scheduling">("identification");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const uploadInFlight = useRef(false);
  const [libraryLoading, setLibraryLoading] = useState(!profile.needsSetup);
  const [transcriptLoading, setTranscriptLoading] = useState(false);
  const [transcriptError, setTranscriptError] = useState<string | null>(null);
  const transcriptRequest = useRef(0);
  const restoredSelection = useRef(false);
  const recorder = useRef<MediaRecorder | null>(null); const stream = useRef<MediaStream | null>(null); const chunks = useRef<Blob[]>([]); const audio = useRef<HTMLAudioElement | null>(null);
  const recordingAppointmentId = useRef<string | null>(null);
  const sessionView = useSyncExternalStore(subscribeToSessionView, readSessionView, () => "cards");
  const selectClientView = (view: "clinical-workspace" | "documents" | "care-settings" | "insights" | "chat") => {
    setActiveClientView(view);
    const url = new URL(window.location.href);
    if (view === "chat") url.searchParams.set("view", "chat");
    else url.searchParams.delete("view");
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  };
  const loadLibrary = useCallback(async () => { setLibraryLoading(true); setTranscripts([]); setTranscript(null); setActiveId(null); try { setLibraryError(null); setTranscripts(profile.clientId ? await api.listTranscripts(profile.clientId) : []); } catch (error) { setLibraryError(error instanceof Error ? error.message : "Could not load saved transcripts."); } finally { setLibraryLoading(false); } }, [profile.clientId]);
  const loadAppointments = useCallback(async () => { try { const response = await fetch(`/api/client-scheduling${profile.clientId ? `?client_id=${encodeURIComponent(profile.clientId)}` : ""}`, { cache: "no-store" }); if (!response.ok) return; const body = await response.json(); setAppointments(body.appointments || []); } catch { /* The transcript library remains usable while scheduling is unavailable. */ } finally { setAppointmentsLoading(false); } }, [profile.clientId]);
  useEffect(() => {
    if (profile.needsSetup) return;
    void Promise.resolve().then(() => { void loadLibrary(); void loadAppointments(); });
  }, [loadLibrary, loadAppointments, profile.needsSetup]); useEffect(() => () => stream.current?.getTracks().forEach((track) => track.stop()), []);
  useEffect(() => {
    if (profile.needsSetup || !profile.clientId) return;
    let cancelled = false;
    void api.listProcessingJobs(profile.clientId)
      .then(jobs => {
        if (cancelled || !jobs.length) return;
        setProcessingJobId(jobs[0].id);
        setProcessingAppointmentId(jobs[0].appointment_id ?? null);
        if (jobs[0].appointment_id) {
          setActiveId(jobs[0].appointment_id);
          setActiveSessionType("scheduled");
        }
        setIsBusy(true);
        setProcessingState(processingStateForStatus(jobs[0].status));
      })
      .catch(error => { if (!cancelled) setUploadError(error instanceof Error ? error.message : "Could not restore session processing status."); });
    return () => { cancelled = true; };
  }, [profile.clientId, profile.needsSetup]);
  useEffect(() => {
    if (!processingJobId || !profile.clientId) return;
    let stopped = false;
    const check = async () => {
      try {
        const job = await api.getJobStatus(processingJobId, profile.clientId!);
        if (stopped) return;
        if (job.status === "COMPLETED") {
          stopped = true;
          window.clearInterval(timer);
          setProcessingJobId(null);
          setProcessingAppointmentId(null);
          setIsBusy(false);
          await Promise.all([loadLibrary(), loadAppointments()]);
          setWorkspaceVisit(visit => visit + 1);
          setProcessingState(null);
          return;
        }
        if (job.status === "FAILED") throw new Error(job.detail || "HealthScribe could not complete the recording.");
        setProcessingState(processingStateForStatus(job.status));
      } catch (error) {
        if (stopped) return;
        stopped = true;
        window.clearInterval(timer);
        setProcessingJobId(null);
        setProcessingAppointmentId(null);
        setIsBusy(false);
        setProcessingState(null);
        await loadAppointments();
        setUploadError(error instanceof Error ? error.message : "Could not restore session processing status.");
      }
    };
    void check();
    const timer = window.setInterval(() => void check(), 5000);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [loadAppointments, loadLibrary, processingJobId, profile.clientId]);
  const openTranscript = async (id: string, message = "Viewing saved transcript.", evidenceSegmentIndex?: number) => {
    if (profile.clientId) rememberClinicalSession(profile.clientId, { id, type: "completed" });
    const request = ++transcriptRequest.current;
    setActiveId(id); setActiveSessionType("completed"); setActiveSegment(evidenceSegmentIndex ?? -1);
    setTranscript(null); setTranscriptLoading(true); setTranscriptError(null);
    try { if (!profile.clientId) throw new Error("This client workspace is unavailable."); const data = await api.getTranscript(id, profile.clientId); if (request === transcriptRequest.current) { setTranscript(data); setStatus(message); } }
    catch (error) { if (request === transcriptRequest.current) setTranscriptError(error instanceof Error ? error.message : "Could not open transcript."); }
    finally { if (request === transcriptRequest.current) setTranscriptLoading(false); }
  };
  const selectScheduled = (id: string | null) => { transcriptRequest.current++; audio.current?.pause(); setActiveId(id); setTranscript(null); setActiveSegment(-1); setTranscriptLoading(false); setActiveSessionType("scheduled"); if (id && profile.clientId) rememberClinicalSession(profile.clientId, { id, type: "scheduled" }); };
  const openClinicalWorkspace = () => {
    const upcoming = nextScheduledSession(transcripts, appointments);
    if (activeSessionType === "scheduled" && activeId !== upcoming?.id) selectScheduled(upcoming?.id ?? null);
    selectClientView("clinical-workspace");
    setWorkspaceVisit(visit => visit + 1);
  };
  const processAudio = async (audioBlob: Blob, appointmentId: string | null) => {
    if (uploadInFlight.current || isBusy) return;
    uploadInFlight.current = true;
    setIsBusy(true);
    setUploadError(null);
    setProcessingState({ phase: "uploading", message: "Uploading securely — please keep this page open.", progress: 0 });
    let handedOff = false;
    try {
      if (!profile.clientId) throw new Error("This client workspace is unavailable.");
      if (!appointmentId) throw new Error("Select the scheduled session that this recording belongs to.");
      setProcessingAppointmentId(appointmentId);
      const job = await api.uploadRecording(audioBlob, profile.clientId, appointmentId, percent => setProcessingState({
        phase: "uploading",
        message: "Uploading securely — please keep this page open.",
        progress: percent,
      }));
      handedOff = true;
      setProcessingJobId(job.id);
      setProcessingState(processingStateForStatus("IN_PROGRESS"));
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Could not process the audio recording.");
    } finally {
      uploadInFlight.current = false;
      if (!handedOff) {
        setProcessingAppointmentId(null);
        setIsBusy(false);
        setProcessingState(null);
      }
    }
  };
  const sendRecording = async () => { stream.current?.getTracks().forEach((track) => track.stop()); setIsRecording(false); const blob = new Blob(chunks.current, { type: recorder.current?.mimeType || "audio/webm" }); const appointmentId = recordingAppointmentId.current; recordingAppointmentId.current = null; await processAudio(blob, appointmentId); };
  const uploadAudio = async (file: File) => {
    if (uploadInFlight.current || isBusy || isRecording) return;
    setUploadError(null);
    if (!/\.(wav|mp3|m4a|mp4|flac|ogg|webm|amr)$/i.test(file.name)) { setUploadError("Choose a WAV, MP3, M4A, MP4, FLAC, Ogg, WebM, or AMR audio file."); return; }
    if (!file.size || file.size > 100 * 1024 * 1024) { setUploadError("Choose a non-empty audio file up to 100 MB."); return; }
    await processAudio(file, activeSessionType === "scheduled" ? activeId : null);
  };
  const toggleRecording = async () => { if (recorder.current?.state === "recording") { recorder.current.stop(); return; } try { stream.current = await navigator.mediaDevices.getUserMedia({ audio: true }); chunks.current = []; recordingAppointmentId.current = activeSessionType === "scheduled" ? activeId : null; const nextRecorder = new MediaRecorder(stream.current); recorder.current = nextRecorder; nextRecorder.addEventListener("dataavailable", (event) => chunks.current.push(event.data)); nextRecorder.addEventListener("stop", () => void sendRecording(), { once: true }); nextRecorder.start(); setIsRecording(true); setStatus("Recording… press Stop when finished."); } catch (error) { recordingAppointmentId.current = null; setStatus(error instanceof Error ? `Microphone unavailable: ${error.message}` : "Microphone unavailable."); } };
  const playSegment = (index: number) => { const player = audio.current; if (!player || !transcript?.recording_url) { setStatus("Audio is not available for this transcript."); return; } if (index === activeSegment) { if (player.paused) void player.play().catch(() => setStatus("Audio playback could not start.")); else player.pause(); return; } player.currentTime = transcript.segments[index].start; setActiveSegment(index); void player.play().catch(() => setStatus("Audio playback could not start.")); };
  useEffect(() => {
    if (libraryLoading || appointmentsLoading || restoredSelection.current) return;
    const upcoming = nextScheduledSession(transcripts, appointments);
    const saved = profile.clientId ? readClinicalSession(profile.clientId) : null;
    const frame = window.requestAnimationFrame(() => {
      if (restoredSelection.current) return;
      restoredSelection.current = true;
      if (saved?.type === "completed" && transcripts.some(item => item.id === saved.id)) void openTranscript(saved.id);
      else selectScheduled(saved?.type === "scheduled" && saved.id === upcoming?.id ? saved.id : upcoming?.id ?? null);
    });
    return () => window.cancelAnimationFrame(frame);
  // Restore exactly once after this client's session library is available.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [libraryLoading, appointmentsLoading, profile.clientId, transcripts, appointments]);
  const transcriptViewer = transcriptLoading ? <LoadingSpinner label="Loading transcript…" /> : transcriptError ? <p role="alert" className="p-5 text-sm text-red-700">{transcriptError}</p> : <TranscriptViewer key={activeId} transcript={transcript} recordContext={recordContext} sessionId={activeId ?? undefined} activeSegment={activeSegment} isPlaying={isPlaying} onPlaySegment={playSegment} onAudioTimeUpdate={(event) => setActiveSegment(transcript?.segments.findIndex((segment) => event.currentTarget.currentTime >= segment.start && event.currentTarget.currentTime < segment.end) ?? -1)} onAudioPlay={() => setIsPlaying(true)} onAudioPause={() => setIsPlaying(false)} onAudioEnded={() => { setIsPlaying(false); setActiveSegment(-1); }} />;
  const upcomingId = processingAppointmentId ?? nextScheduledSession(transcripts, appointments)?.id;
  const showPreparation = Boolean(upcomingId && activeId === upcomingId);
  const activeSessionLayout = activeSessionType === "scheduled" ? showPreparation && processingState?.phase !== "processing" ? <ScheduledSessionLayout isRecording={isRecording} isBusy={isBusy} processingState={processingState} processingError={uploadError} hasPriorSessions={transcripts.length > 0} onToggleRecording={() => void toggleRecording()} onUploadAudio={file => void uploadAudio(file)} onViewEvidence={(source: BriefEvidence) => void openTranscript(source.session_id, `Reviewing cited evidence from ${source.session_label}.`, source.segment_index)} recordContext={recordContext} /> : null : <CompletedSessionLayout>{transcriptViewer}</CompletedSessionLayout>;

  if (newClientSetup) return <main className="mx-auto w-[min(92vw,1080px)] pt-3 pb-8 text-center">
    <CareRelationshipHeader profile={profile} actions={[]} activeAction="" />
    {configuringSessions ? <ClientCareSettings initialSection="scheduling" clientId={profile.clientId || undefined} expandRecurring onScheduleChanged={() => { void loadAppointments(); setNewClientSetup(false); }} /> : <section className="relative overflow-hidden rounded-2xl border border-stone-200 bg-stone-50 shadow-sm" aria-label="Configure this client's sessions">
      <div aria-hidden="true" className="pointer-events-none select-none blur-[2px] opacity-90"><SessionCardCarousel transcripts={[]} appointments={setupAppointments} activeId={setupAppointments[0]?.id || null} error={null} onOpen={() => {}} onSelectScheduled={() => {}} /></div>
      <div className="absolute inset-0 z-20 grid place-items-center"><button type="button" onClick={() => setConfiguringSessions(true)} className="cursor-grab rounded-xl border border-emerald-900 bg-emerald-800 px-5 py-3 text-sm font-semibold text-white shadow-lg transition-colors duration-200 hover:bg-emerald-900 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Configure sessions</button></div>
    </section>}
  </main>;


  return (
    <main className="mx-auto w-[min(92vw,1080px)] pt-3 pb-8 text-center">
      <CareRelationshipHeader profile={profile} activeAction={activeClientView} actions={[
        { id: "clinical-workspace", label: "Clinical workspace", icon: "workspace", onSelect: openClinicalWorkspace },
        { id: "billing", label: "Billing", icon: "billing", comingSoon: true },
        { id: "documents", label: "Documents", icon: "documents", onSelect: () => selectClientView("documents") },
        { id: "insights", label: "Insights", icon: "insights", onSelect: () => selectClientView("insights") },
        { id: "care-settings", label: "Client care settings", icon: "settings", onSelect: () => { setCareSettingsSection("identification"); selectClientView("care-settings"); } },
        { id: "chat", label: "Chat", icon: "chat", onSelect: () => selectClientView("chat") },
      ]} />
      <div id="clinical-workspace" className="scroll-mt-6">
        {activeClientView === "chat" ? <CareChat partnerName={profile.name} /> : activeClientView === "insights" ? <><ClientInsights recordContext={recordContext} onViewEvidence={(source) => { setActiveClientView("clinical-workspace"); void openTranscript(source.session_id, `Reviewing cited evidence from ${source.session_label}.`, source.segment_index); }} />{recordContext && <ClientJourney recordContext={recordContext} onViewEvidence={(source) => { setActiveClientView("clinical-workspace"); void openTranscript(source.session_id, `Reviewing cited evidence from ${source.session_label}.`, source.segment_index); }} />}</> : activeClientView === "documents" ? recordContext ? <ClientDocuments recordContext={recordContext} /> : <p role="alert" className="text-sm text-red-700">This client document library is unavailable.</p> : activeClientView === "care-settings" ? <ClientCareSettings initialSection={careSettingsSection} clientId={profile.clientId || undefined} onScheduleChanged={() => void loadAppointments()} />  : libraryLoading ? <LoadingSpinner label="Loading sessions…" /> : sessionView === "cards" ? <><SessionCardCarousel key={`${workspaceVisit}-${processingAppointmentId ?? "idle"}`} transcripts={transcripts} appointments={appointments} activeId={activeId ?? processingAppointmentId ?? nextScheduledSession(transcripts, appointments)?.id ?? null} error={libraryError} processingSession={processingAppointmentId && processingState?.phase === "processing" ? { appointmentId: processingAppointmentId, state: processingState } : null} onOpen={(id) => void openTranscript(id)} onSelectScheduled={session => selectScheduled(session.id)} onEditSchedule={() => { setCareSettingsSection("scheduling"); setActiveClientView("care-settings"); }} /><div className="mt-6 text-left" ref={(node) => { audio.current = node?.querySelector("audio") ?? null; }}>{activeSessionLayout}</div></> : <div className="mt-6 grid items-start gap-6 text-left md:grid-cols-[minmax(380px,440px)_minmax(0,1fr)]"><TranscriptLibrary transcripts={transcripts} activeId={activeId} error={libraryError} onOpen={(id) => void openTranscript(id)} /><div className="min-w-0" ref={(node) => { audio.current = node?.querySelector("audio") ?? null; }}>{activeSessionLayout}</div></div>}
      </div>
    </main>
  );
}
