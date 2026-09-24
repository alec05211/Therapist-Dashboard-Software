"use client";
import { useEffect, useState } from "react";
import { CareRelationshipHeader, type CareProfile } from "@/components/care-relationship-header";
import { SessionCardCarousel, nextScheduledSession, type SessionCard } from "@/components/session-review/session-card-carousel";
import { CompletedSessionLayout } from "@/components/session-review/completed-session-layout";
import { TranscriptViewer } from "@/components/session-review/transcript-viewer";
import { ClientDocumentRelationships } from "@/components/client-document-relationships";
import { CareChat } from "@/components/care-chat";
import { LoadingSpinner } from "@/components/loading-spinner";

type Portal = {
  permissions: Record<"can_view_session_history" | "can_view_shared_transcripts" | "can_view_insights" | "can_view_draft_notes" | "can_play_shared_recordings", boolean>;
  sessions?: { id: string; label: string; created_at?: string; recording_url?: string; segments?: { speaker: string; text: string; start: number; end: number }[]; draft_note?: { name: string; items: string[] }[] }[];
  insights?: string[];
};

export function ClientPortal({ name, profile }: { name: string; profile: CareProfile }) {
  const [activeView, setActiveView] = useState("clinical-workspace");
  const [portal, setPortal] = useState<Portal | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [workspaceVisit, setWorkspaceVisit] = useState(0);
  const [chosenScheduled, setScheduled] = useState<SessionCard | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    let sequence = 0;
    const load = async () => {
      const current = ++sequence;
      try {
        const response = await fetch("/api/client-portal", { cache: "no-store" });
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail || "Could not load shared materials.");
        if (active && current === sequence) { setPortal(body); setError(null); }
      } catch (reason) { if (active && current === sequence) { setPortal(null); setError(reason instanceof Error ? reason.message : "Could not load shared materials."); } }
    };
    void load();
    window.addEventListener("focus", load);
    const timer = window.setInterval(load, 60000);
    return () => { active = false; window.removeEventListener("focus", load); window.clearInterval(timer); };
  }, []);
  const carouselSessions = (portal?.sessions ?? []).map(session => ({ id: session.id, label: session.label, created_at: session.created_at ?? "", text: "" }));
  const scheduled = chosenScheduled ?? (!selectedId && portal?.permissions.can_view_session_history ? nextScheduledSession(carouselSessions) : null);
  const latestSession = portal?.sessions?.at(-1);
  const selectedSession = portal?.sessions?.find(session => session.id === selectedId) ?? latestSession;
  const visibleSessions = portal?.permissions.can_view_session_history
    ? scheduled ? [] : selectedSession ? [selectedSession] : []
    : portal?.sessions ?? [];
  return <main className="mx-auto w-[min(92vw,1080px)] py-8 text-stone-900">
    <CareRelationshipHeader profile={profile} activeAction={activeView} actions={[
      { id: "clinical-workspace", label: "Clinical workspace", icon: "workspace", onSelect: () => { setActiveView("clinical-workspace"); setSelectedId(null); setScheduled(null); setWorkspaceVisit(value => value + 1); document.getElementById("client-clinical-workspace")?.focus(); } },
      { id: "documents", label: "Documents", icon: "documents", onSelect: () => setActiveView("documents") },
      { id: "chat", label: "Chat", icon: "chat", onSelect: () => setActiveView("chat") },
      { id: "prescriptions", label: "Prescriptions", icon: "prescriptions", comingSoon: true },
    ]} />
    {activeView === "documents" ? <ClientDocumentRelationships /> : activeView === "chat" ? <CareChat partnerName={profile.name} /> : <section id="client-clinical-workspace" tabIndex={-1} className="outline-none">
    <p className="sr-only">{name}’s clinical workspace</p>
    {error && <p role="alert" className="mt-5">{error}</p>}{!portal && !error && <LoadingSpinner label="Loading shared materials…" />}
    {portal && <>
      {!Object.values(portal.permissions).some(Boolean) && <p className="mt-5">Your therapist has not enabled shared materials.</p>}
      {portal.permissions.can_view_session_history && <div className="mt-6">
        <SessionCardCarousel key={workspaceVisit}
          transcripts={carouselSessions}
          activeId={scheduled?.id ?? selectedSession?.id ?? null}
          error={null}
          onOpen={id => { setSelectedId(id); setScheduled(null); }}
          onSelectScheduled={session => { setScheduled(session); setSelectedId(null); }}
        />
        {scheduled ? <section className="mt-6 rounded-2xl border border-stone-200 bg-stone-50 p-5" aria-label="Upcoming session">
          <p className="text-sm font-medium text-emerald-800">Upcoming session</p>
          <h2 className="mt-1 text-xl font-semibold">{scheduled.date.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}</h2>
          <p className="mt-2 text-sm text-stone-600">With {profile.name} · {scheduled.date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZoneName: "short" })}</p>
          <p className="mt-3 text-sm leading-6 text-stone-600">Planned session in your synthetic care schedule. Session details are pending.</p>
        </section> : null}
      </div>}
      {(portal.permissions.can_view_shared_transcripts || portal.permissions.can_view_draft_notes) && visibleSessions.map(session => <div key={session.id} className="mt-6"><CompletedSessionLayout sessionId={session.label}>
        <TranscriptViewer key={session.id}
          showTranscript={portal.permissions.can_view_shared_transcripts}
          showClinicalNote={portal.permissions.can_view_draft_notes}
          transcript={{ id: session.id, speakers: {}, segments: session.segments ?? [], recording_url: session.recording_url ? `/api${session.recording_url}` : undefined, clinical_note: session.draft_note ?? [] }} />
      </CompletedSessionLayout></div>)}
      {portal.permissions.can_view_insights && <section className="mt-7"><h2 className="text-xl font-semibold">Therapist-approved insights</h2><p className="mt-2 text-sm text-stone-600">Reflections for discussion with your therapist.</p>{portal.insights?.length ? portal.insights.map((text, index) => <p key={index} className="mt-3 leading-6">{text}</p>) : <p className="mt-3">No therapist-approved insights have been shared yet.</p>}</section>}

    </>}
  </section>}</main>;
}
