"use client";

import { useEffect, useState } from "react";
import { LoadingSpinner } from "@/components/loading-spinner";

type Props = { onReturnToWorkspace: () => void };
type Section = "profile" | "schedule" | "permissions";
type Permission = "history" | "transcript" | "insights" | "draftNotes" | "recordings";

const permissions: { id: Permission; title: string; detail: string }[] = [
  { id: "history", title: "Session history", detail: "Show past session history." },
  { id: "transcript", title: "Transcript", detail: "Allow transcripts for shared sessions." },
  { id: "recordings", title: "Recording playback", detail: "Allow audio playback and download alongside shared transcripts." },
  { id: "insights", title: "Insights", detail: "Allow therapist-approved insights only." },
  { id: "draftNotes", title: "Draft note", detail: "Keep off unless a draft is intentionally shared." },
];

export function ClientCareSettings({ onReturnToWorkspace }: Props) {
  const [section, setSection] = useState<Section>("profile");
  const [context, setContext] = useState<{ organization_id: string; client_id: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [choices, setChoices] = useState<Record<Permission, boolean>>({ history: false, transcript: false, insights: false, draftNotes: false, recordings: false });
  const [saved, setSaved] = useState(false);
  const fields = { history: "can_view_session_history", transcript: "can_view_shared_transcripts", insights: "can_view_insights", draftNotes: "can_view_draft_notes", recordings: "can_play_shared_recordings" } as const;
  useEffect(() => {
    let active = true;
    void fetch("/api/client-portal-permissions", { cache: "no-store" }).then(async (response) => {
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Could not load permissions.");
      if (active) { setContext(body); setChoices({ history: body.can_view_session_history, transcript: body.can_view_shared_transcripts, insights: body.can_view_insights, draftNotes: body.can_view_draft_notes, recordings: body.can_play_shared_recordings }); }
    }).catch((reason: Error) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, []);
  const save = async () => {
    if (!context || busy) return;
    setBusy(true); setSaved(false); setError(null);
    try {
      const response = await fetch("/api/client-portal-permissions", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ organization_id: context.organization_id, client_id: context.client_id, ...Object.fromEntries(Object.entries(fields).map(([key, field]) => [field, choices[key as Permission]])) }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Could not save permissions.");
      setSaved(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save permissions."); }
    finally { setBusy(false); }
  };
  const toggle = (id: Permission) => { setSaved(false); setChoices((value) => ({ ...value, [id]: !value[id] })); };

  return <section className="rounded-2xl border border-stone-200 bg-white text-left shadow-sm" aria-labelledby="client-care-settings-title">
    <div className="p-5 sm:p-7"><p className="text-sm font-medium text-emerald-800">Elena Sadić · Client settings</p><h2 id="client-care-settings-title" className="mt-1 text-xl font-semibold tracking-tight text-stone-900">Client care settings</h2><p className="mt-2 text-sm leading-6 text-stone-600">Manage care details and the client-facing experience separately from your own account.</p></div>
    <nav className="flex gap-1 overflow-x-auto border-y border-stone-200 bg-stone-50 px-3 py-2" aria-label="Client settings sections">{(["profile", "schedule", "permissions"] as Section[]).map((id) => <button key={id} type="button" onClick={() => { setSection(id); setSaved(false); }} className={`cursor-grab rounded-lg px-3 py-2 text-sm font-semibold capitalize transition-colors duration-200 ease-out focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing ${section === id ? "bg-emerald-50 text-emerald-900" : "text-stone-600 hover:bg-stone-100"}`}>{id === "schedule" ? "Scheduling" : id}</button>)}</nav>
    <div className="p-5 sm:p-7">{section === "profile" && <div className="rounded-xl border border-stone-200 p-4"><h3 className="text-sm font-semibold text-stone-900">Profile</h3><p className="mt-2 text-sm leading-6 text-stone-600">Preferred name and client-identification controls will live here.</p></div>}{section === "schedule" && <div className="rounded-xl border border-stone-200 p-4"><h3 className="text-sm font-semibold text-stone-900">Scheduling</h3><p className="mt-2 text-sm leading-6 text-stone-600">Session cadence and appointment preferences will live here.</p></div>}{section === "permissions" && <div><p className="text-sm leading-6 text-stone-600">Choose what Elena can see in her portal. Changes apply to this synthetic relationship.</p><div className="mt-5 grid gap-3">{permissions.map((permission) => <label key={permission.id} className="flex cursor-grab items-start justify-between gap-5 rounded-xl border border-stone-200 p-4 transition-colors duration-200 ease-out hover:bg-stone-50 active:cursor-grabbing"><span><span className="block text-sm font-semibold text-stone-900">{permission.title}</span><span className="mt-1 block text-xs leading-5 text-stone-500">{permission.detail}</span></span><input type="checkbox" disabled={!context || busy} checked={choices[permission.id]} onChange={() => toggle(permission.id)} className="mt-0.5 size-4 accent-emerald-700" /></label>)}</div></div>}<div className="mt-6 flex items-center justify-between gap-4 border-t border-stone-200 pt-5"><button type="button" onClick={onReturnToWorkspace} className="cursor-grab rounded-lg px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing">Return to workspace</button><button type="button" disabled={!context || busy || section !== "permissions"} onClick={() => void save()} className="cursor-grab rounded-lg bg-emerald-800 px-3.5 py-2 text-sm font-semibold text-white hover:bg-emerald-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing">{busy ? "Saving…" : "Save changes"}</button></div>{error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}{!context && !error && <LoadingSpinner label="Loading permissions…" />}{saved && <p className="mt-3 text-right text-sm font-medium text-emerald-800" role="status">Sharing permissions saved.</p>}</div>
  </section>;
}
