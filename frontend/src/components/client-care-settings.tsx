"use client";

import { useEffect, useRef, useState } from "react";
import { LoadingSpinner } from "@/components/loading-spinner";
import { SettingsLayout, settingsFieldClass, type SettingsSection } from "@/components/settings-layout";

type Props = { onReturnToWorkspace: () => void };
type Section = "identification" | "scheduling" | "permissions";
type Permission = "history" | "transcript" | "insights" | "draftNotes" | "recordings";
type AudioSample = { recordingUrl: string; start: number; end: number };
type Participant = { name: string; sample: AudioSample | null };

const sections: SettingsSection[] = [
  { id: "identification", title: "Identification" },
  { id: "scheduling", title: "Scheduling" },
  { id: "permissions", title: "Permissions" },
];

const permissions: { id: Permission; title: string; detail: string }[] = [
  { id: "history", title: "Session history", detail: "Show past session history." },
  { id: "transcript", title: "Transcript", detail: "Allow transcripts for shared sessions." },
  { id: "recordings", title: "Recording playback", detail: "Allow audio playback alongside shared transcripts." },
  { id: "insights", title: "Insights", detail: "Allow therapist-approved insights only." },
  { id: "draftNotes", title: "Draft note", detail: "Keep off unless a draft is intentionally shared." },
];

const permissionFields = { history: "can_view_session_history", transcript: "can_view_shared_transcripts", insights: "can_view_insights", draftNotes: "can_view_draft_notes", recordings: "can_play_shared_recordings" } as const;

function VolumeIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="size-4"><path strokeLinecap="round" strokeLinejoin="round" d="M11 5 6.8 8.5H3.5v7h3.3L11 19V5Z" /><path strokeLinecap="round" d="M15 9.25a4 4 0 0 1 0 5.5M17.75 6.75a7.5 7.5 0 0 1 0 10.5" /></svg>;
}

function ParticipantFields({ id, value, playing, onChange, onPlay }: { id: string; value: Participant; playing: boolean; onChange: (value: Participant) => void; onPlay: () => void }) {
  return <fieldset className="grid grid-cols-[minmax(0,1fr)_2.5rem] items-center gap-2 py-2.5">
    <legend className="sr-only">Speaker identification</legend>
    <label className="sr-only" htmlFor={`${id}-name`}>Name</label>
    <input id={`${id}-name`} aria-label="Name" required maxLength={200} placeholder="Name" value={value.name} onChange={(event) => onChange({ ...value, name: event.target.value })} className={`${settingsFieldClass} mt-0 min-w-0`} />
    <button type="button" onClick={onPlay} disabled={!value.sample} aria-label={playing ? "Pause speaker sample" : "Play speaker sample"} title={value.sample ? "Play a short sample from a labeled session" : "Label this speaker in a completed session to create a sample"} className={`grid size-10 place-items-center rounded-lg border border-stone-300 bg-white transition-colors duration-200 ease-out focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${value.sample ? "cursor-grab text-stone-600 hover:border-stone-400 hover:bg-stone-100 hover:text-stone-900 active:cursor-grabbing" : "cursor-not-allowed text-stone-300"}`}><VolumeIcon /></button>
  </fieldset>;
}

export function ClientCareSettings({ onReturnToWorkspace }: Props) {
  const [section, setSection] = useState<Section>("identification");
  const [context, setContext] = useState<{ organization_id: string; client_id: string } | null>(null);
  const [client, setClient] = useState<Participant>({ name: "", sample: null });
  const [therapist, setTherapist] = useState<Participant>({ name: "", sample: null });
  const [activeSample, setActiveSample] = useState<(AudioSample & { id: string }) | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const [choices, setChoices] = useState<Record<Permission, boolean>>({ history: false, transcript: false, insights: false, draftNotes: false, recordings: false });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let active = true;
    void Promise.all([
      fetch("/api/client-portal-permissions", { cache: "no-store" }),
      fetch("/api/client-identification", { cache: "no-store" }),
    ]).then(async ([permissionResponse, identificationResponse]) => {
      const permissionBody = await permissionResponse.json();
      const identificationBody = await identificationResponse.json();
      if (!permissionResponse.ok) throw new Error(permissionBody.detail || "Could not load permissions.");
      if (!identificationResponse.ok) throw new Error(identificationBody.detail || "Could not load identification.");
      if (!active) return;
      setContext({ organization_id: permissionBody.organization_id, client_id: permissionBody.client_id });
      setChoices({ history: permissionBody.can_view_session_history, transcript: permissionBody.can_view_shared_transcripts, insights: permissionBody.can_view_insights, draftNotes: permissionBody.can_view_draft_notes, recordings: permissionBody.can_play_shared_recordings });
      setClient({ name: identificationBody.client.name, sample: identificationBody.client.sample ?? null });
      setTherapist({ name: identificationBody.therapist.name, sample: identificationBody.therapist.sample ?? null });
    }).catch((reason: Error) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, []);

  const save = async () => {
    if (!context || busy || section === "scheduling") return;
    setBusy(true); setSaved(false); setError(null);
    try {
      const response = section === "identification"
        ? await fetch("/api/client-identification", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...context, client: { name: client.name }, therapist: { name: therapist.name } }) })
        : await fetch("/api/client-portal-permissions", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...context, ...Object.fromEntries(Object.entries(permissionFields).map(([key, field]) => [field, choices[key as Permission]])) }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Could not save client care settings.");
      if (section === "identification") {
        setClient({ name: body.client.name, sample: body.client.sample ?? null });
        setTherapist({ name: body.therapist.name, sample: body.therapist.sample ?? null });
      }
      setSaved(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save client care settings."); }
    finally { setBusy(false); }
  };

  const ready = Boolean(context);
  const canSave = ready && !busy && section !== "scheduling" && (section !== "identification" || Boolean(client.name.trim() && therapist.name.trim()));

  const toggleSample = (id: string, sample: AudioSample | null) => {
    if (!sample) return;
    if (activeSample?.id === id) {
      audioRef.current?.pause();
      setActiveSample(null);
      return;
    }
    audioRef.current?.pause();
    setActiveSample({ ...sample, id });
  };

  return <SettingsLayout sections={sections} activeSection={section} onSelect={(id) => { audioRef.current?.pause(); setActiveSample(null); setSection(id as Section); setSaved(false); setError(null); }} navigationLabel="Client care setting sections" headingLevel="h2">
    {!ready && !error ? <LoadingSpinner label="Loading client settings…" /> : null}
    {ready && section === "identification" ? <div className="mt-4 divide-y divide-stone-200"><ParticipantFields id="speaker-one" value={client} playing={activeSample?.id === "speaker-one"} onPlay={() => toggleSample("speaker-one", client.sample)} onChange={(value) => { setClient(value); setSaved(false); }} /><ParticipantFields id="speaker-two" value={therapist} playing={activeSample?.id === "speaker-two"} onPlay={() => toggleSample("speaker-two", therapist.sample)} onChange={(value) => { setTherapist(value); setSaved(false); }} /></div> : null}
    {ready && section === "scheduling" ? <div className="mt-6 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm text-stone-600">Scheduling preferences are coming soon.</div> : null}
    {ready && section === "permissions" ? <div className="mt-6 grid gap-3">{permissions.map((permission) => <label key={permission.id} className="flex cursor-grab items-start justify-between gap-5 rounded-xl border border-stone-200 bg-stone-50 p-4 transition-colors duration-200 ease-out hover:bg-stone-100 active:cursor-grabbing"><span><span className="block text-sm font-semibold text-stone-900">{permission.title}</span><span className="mt-1 block text-xs leading-5 text-stone-500">{permission.detail}</span></span><input type="checkbox" disabled={busy} checked={choices[permission.id]} onChange={() => { setChoices((value) => ({ ...value, [permission.id]: !value[permission.id] })); setSaved(false); }} className="mt-0.5 size-4 accent-emerald-700" /></label>)}</div> : null}
    <div className="mt-6 flex items-center justify-between gap-4 border-t border-stone-200 pt-5"><button type="button" onClick={onReturnToWorkspace} className="cursor-grab rounded-lg px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing">Return to workspace</button><button type="button" disabled={!canSave} onClick={() => void save()} className="cursor-grab rounded-lg bg-emerald-800 px-3.5 py-2 text-sm font-semibold text-white hover:bg-emerald-900 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing">{busy ? "Saving…" : "Save changes"}</button></div>
    {error ? <p role="alert" className="mt-3 text-sm text-red-700">{error}</p> : null}
    {saved ? <p className="mt-3 text-right text-sm font-medium text-emerald-800" role="status">Client care settings saved.</p> : null}
    {activeSample ? <audio key={`${activeSample.id}-${activeSample.recordingUrl}-${activeSample.start}`} ref={audioRef} className="sr-only" src={activeSample.recordingUrl} onCanPlay={(event) => { event.currentTarget.currentTime = activeSample.start; void event.currentTarget.play().catch(() => { setError("The speaker sample could not be played."); setActiveSample(null); }); }} onTimeUpdate={(event) => { if (event.currentTarget.currentTime >= activeSample.end) { event.currentTarget.pause(); setActiveSample(null); } }} onEnded={() => setActiveSample(null)} onError={() => { setError("The speaker sample is unavailable."); setActiveSample(null); }} /> : null}
  </SettingsLayout>;
}
