"use client";

import { useEffect, useRef, useState } from "react";
import { LoadingSpinner } from "@/components/loading-spinner";
import { SettingsLayout, settingsFieldClass, type SettingsSection } from "@/components/settings-layout";
import { ClientScheduling } from "@/components/client-scheduling";

type Section = "identification" | "scheduling" | "permissions";
type Permission = "transcript" | "insights" | "clinicalNote" | "recordings" | "prescriptions";
type AudioSample = { recordingUrl: string; start: number; end: number };
type Participant = { name: string; pronouns: string; sample: AudioSample | null };
type SpeakerAssociation = { transcriptVersionId: string; sessionId: string; sessionLabel: string; sourceLabel: string; name: string; sample: AudioSample | null; overridden: boolean };

const sections: SettingsSection[] = [
  { id: "identification", title: "Identification" },
  { id: "scheduling", title: "Scheduling" },
  { id: "permissions", title: "Permissions" },
];

const permissions: { id: Permission; title: string; detail: string }[] = [
  { id: "transcript", title: "Transcripts", detail: "Allow the client to review transcripts from completed sessions." },
  { id: "recordings", title: "Recording playback", detail: "Allow audio playback alongside a shared transcript." },
  { id: "clinicalNote", title: "Clinical notes", detail: "Share draft clinical notes for the client to review." },
  { id: "insights", title: "Insights", detail: "Share only insights the therapist has approved." },
  { id: "prescriptions", title: "Prescriptions", detail: "Show the prescriptions view in the client portal." },
];

const permissionFields = { transcript: "can_view_shared_transcripts", insights: "can_view_insights", clinicalNote: "can_view_draft_notes", recordings: "can_play_shared_recordings", prescriptions: "can_view_prescriptions" } as const;

function VolumeIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="size-4"><path strokeLinecap="round" strokeLinejoin="round" d="M11 5 6.8 8.5H3.5v7h3.3L11 19V5Z" /><path strokeLinecap="round" d="M15 9.25a4 4 0 0 1 0 5.5M17.75 6.75a7.5 7.5 0 0 1 0 10.5" /></svg>;
}

function IdentificationRow({ id, label, name, sample, playing, suggestions, onChange, onPlay }: { id: string; label: string; name: string; sample: AudioSample | null; playing: boolean; suggestions: string[]; onChange: (name: string) => void; onPlay: () => void }) {
  return <div className="grid items-center gap-2 py-2.5 text-left sm:grid-cols-[6.5rem_minmax(0,1fr)_minmax(8rem,0.55fr)_2.5rem]">
    <div className="min-w-0 break-words text-sm font-semibold text-stone-800">{label}</div>
    <label className="sr-only" htmlFor={`${id}-name`}>{label} name</label>
    <input id={`${id}-name`} list={`${id}-suggestions`} maxLength={200} placeholder="Choose or enter a name" value={name} onChange={(event) => onChange(event.target.value)} className={`${settingsFieldClass} mt-0 min-w-0 sm:col-span-2`} />
    <datalist id={`${id}-suggestions`}>{suggestions.map(suggestion => <option key={suggestion} value={suggestion} />)}</datalist>
    <button type="button" onClick={onPlay} disabled={!sample} aria-label={`${playing ? "Pause" : "Play"} ${label.toLowerCase()} audio sample`} title={sample ? `${playing ? "Pause" : "Play"} a brief ${label.toLowerCase()} audio sample` : `No ${label.toLowerCase()} audio sample is available`} className={`grid size-10 place-items-center rounded-lg border border-stone-300 bg-white transition-colors duration-200 ease-out focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${sample ? `cursor-grab hover:border-stone-400 hover:bg-stone-100 active:cursor-grabbing ${playing ? "border-emerald-700 bg-emerald-50 text-emerald-800" : "text-stone-600 hover:text-stone-900"}` : "cursor-not-allowed text-stone-300"}`}><VolumeIcon /></button>
  </div>;
}

async function responseBody(response: Response, fallback: string) {
  const text = await response.text();
  let body: Record<string, unknown> = {};
  if (text) {
    try { body = JSON.parse(text) as Record<string, unknown>; }
    catch { if (!response.ok) throw new Error(fallback); }
  }
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : fallback);
  return body;
}

export function ClientCareSettings({ initialSection = "identification", clientId, expandRecurring = false, onScheduleChanged }: { initialSection?: Section; clientId?: string; expandRecurring?: boolean; onScheduleChanged?: () => void }) {
  const setupSchedulingOnly = expandRecurring && initialSection === "scheduling";
  const [section, setSection] = useState<Section>(initialSection);
  const [context, setContext] = useState<{ organization_id: string; client_id: string } | null>(null);
  const [client, setClient] = useState<Participant>({ name: "", pronouns: "", sample: null });
  const [therapist, setTherapist] = useState<Participant>({ name: "", pronouns: "", sample: null });
  const [speakers, setSpeakers] = useState<SpeakerAssociation[]>([]);
  const [activeSample, setActiveSample] = useState<(AudioSample & { id: string }) | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const [choices, setChoices] = useState<Record<Permission, boolean>>({ transcript: false, insights: false, clinicalNote: false, recordings: false, prescriptions: false });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [identificationLoading, setIdentificationLoading] = useState(!setupSchedulingOnly);
  const [permissionsLoading, setPermissionsLoading] = useState(!setupSchedulingOnly);
  const [identificationError, setIdentificationError] = useState<string | null>(null);
  const [permissionsError, setPermissionsError] = useState<string | null>(null);

  useEffect(() => {
    if (setupSchedulingOnly) return;
    if (!clientId) {
      void Promise.resolve().then(() => {
        setIdentificationError("This client workspace is unavailable.");
        setPermissionsError("This client workspace is unavailable.");
        setIdentificationLoading(false);
        setPermissionsLoading(false);
      });
      return;
    }
    let active = true;
    const query = `?client_id=${encodeURIComponent(clientId)}`;
    void fetch(`/api/client-identification${query}`, { cache: "no-store" })
      .then(response => responseBody(response, "Could not load identification settings."))
      .then(body => {
        if (!active) return;
        const clientBody = body.client as Participant;
        const therapistBody = body.therapist as Participant;
        setContext({ organization_id: String(body.organization_id), client_id: String(body.client_id) });
        setClient({ name: clientBody.name, pronouns: clientBody.pronouns ?? "", sample: clientBody.sample ?? null });
        setTherapist({ name: therapistBody.name, pronouns: therapistBody.pronouns ?? "", sample: therapistBody.sample ?? null });
        setSpeakers((body.speakers as SpeakerAssociation[] | undefined) ?? []);
      })
      .catch((reason: Error) => { if (active) setIdentificationError(reason.message); })
      .finally(() => { if (active) setIdentificationLoading(false); });
    void fetch(`/api/client-portal-permissions${query}`, { cache: "no-store" })
      .then(response => responseBody(response, "Could not load permission settings."))
      .then(body => {
        if (!active) return;
        setContext({ organization_id: String(body.organization_id), client_id: String(body.client_id) });
        setChoices({ transcript: Boolean(body.can_view_shared_transcripts), insights: Boolean(body.can_view_insights), clinicalNote: Boolean(body.can_view_draft_notes), recordings: Boolean(body.can_play_shared_recordings), prescriptions: Boolean(body.can_view_prescriptions) });
      })
      .catch((reason: Error) => { if (active) setPermissionsError(reason.message); })
      .finally(() => { if (active) setPermissionsLoading(false); });
    return () => { active = false; };
  }, [clientId, setupSchedulingOnly]);

  const save = async () => {
    if (!context || busy || section === "scheduling") return;
    setBusy(true); setSaved(false); setError(null);
    try {
      const response = section === "identification"
        ? await fetch("/api/client-identification", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...context, client: { name: client.name, pronouns: client.pronouns || null }, therapist: { name: therapist.name, pronouns: therapist.pronouns || null }, speakers: speakers.map(({ transcriptVersionId, sourceLabel, name }) => ({ transcript_version_id: transcriptVersionId, source_label: sourceLabel, name })) }) })
        : await fetch("/api/client-portal-permissions", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...context, ...Object.fromEntries(Object.entries(permissionFields).map(([key, field]) => [field, choices[key as Permission]])) }) });
      const body = await responseBody(response, "Could not save client care settings.");
      if (section === "identification") {
        audioRef.current?.pause(); setActiveSample(null);
        const clientBody = body.client as Participant;
        const therapistBody = body.therapist as Participant;
        setClient({ name: clientBody.name, pronouns: clientBody.pronouns ?? "", sample: clientBody.sample ?? null });
        setTherapist({ name: therapistBody.name, pronouns: therapistBody.pronouns ?? "", sample: therapistBody.sample ?? null });
        setSpeakers((body.speakers as SpeakerAssociation[] | undefined) ?? []);
      }
      setSaved(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save client care settings."); }
    finally { setBusy(false); }
  };

  const sectionLoading = section === "identification" ? identificationLoading : section === "permissions" ? permissionsLoading : false;
  const sectionError = section === "identification" ? identificationError : section === "permissions" ? permissionsError : null;
  const sectionReady = section === "scheduling" || (Boolean(context) && !sectionLoading && !sectionError);
  const canSave = sectionReady && !busy && section !== "scheduling";

  const toggleSample = (id: string, sample: AudioSample | null) => {
    const player = audioRef.current;
    if (!sample || !player) return;
    if (activeSample?.id === id) {
      player.pause();
      setActiveSample(null);
      return;
    }
    player.pause();
    player.src = sample.recordingUrl;
    player.addEventListener("loadedmetadata", () => { player.currentTime = sample.start; }, { once: true });
    player.load();
    setActiveSample({ ...sample, id });
    void player.play().catch((reason: unknown) => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setError("The speaker sample could not be played.");
      setActiveSample(null);
    });
  };

  return <SettingsLayout sections={expandRecurring ? sections.filter(item => item.id === "scheduling") : sections} activeSection={section} onSelect={(id) => { audioRef.current?.pause(); setActiveSample(null); setSection(id as Section); setSaved(false); setError(null); }} navigationLabel="Client care setting sections" headingLevel="h2">
    {sectionLoading ? <LoadingSpinner label={`Loading ${section.toLowerCase()} settings…`} /> : null}
    {sectionError ? <p role="alert" className="mt-5 text-sm text-red-700">{sectionError}</p> : null}
    {sectionReady && section === "identification" ? <div className="mt-4 text-left">
      <p className="text-sm leading-6 text-stone-600">HealthScribe separates voices but does not reliably identify people. Each row shows its exact speaker label; assign a name once to use it for the same label throughout this client relationship.</p>
      {speakers.length ? <div className="mt-4 space-y-4">{Array.from(new Set(speakers.map(speaker => speaker.transcriptVersionId))).map(transcriptVersionId => {
        const sessionSpeakers = speakers.filter(speaker => speaker.transcriptVersionId === transcriptVersionId);
        return <section key={transcriptVersionId} className="overflow-hidden rounded-xl border border-stone-200 bg-stone-50">
          <h3 className="border-b border-stone-200 px-4 py-3 text-sm font-semibold text-stone-900">{sessionSpeakers[0]?.sessionLabel ?? "Completed session"}</h3>
          <div className="divide-y divide-stone-200 px-4">{sessionSpeakers.map((speaker) => {
            const id = `speaker-${speaker.transcriptVersionId}-${speaker.sourceLabel}`;
            return <IdentificationRow key={`${speaker.transcriptVersionId}-${speaker.sourceLabel}`} id={id} label={speaker.sourceLabel} name={speaker.name} sample={speaker.sample} suggestions={[client.name, therapist.name].filter(Boolean)} playing={activeSample?.id === id} onPlay={() => toggleSample(id, speaker.sample)} onChange={(name) => { setSpeakers(current => current.map(item => item.sourceLabel.toUpperCase() === speaker.sourceLabel.toUpperCase() ? { ...item, name } : item)); setSaved(false); }} />;
          })}</div>
        </section>;
      })}</div> : <p className="mt-4 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm text-stone-600">Speaker samples will appear after the first session finishes processing.</p>}
    </div> : null}
    {section === "scheduling" ? <ClientScheduling clientId={clientId} initiallyExpanded={expandRecurring} onChanged={onScheduleChanged} /> : null}
    {sectionReady && section === "permissions" ? <div className="mt-6 text-left">
      <div className="divide-y divide-stone-200 overflow-hidden rounded-xl border border-stone-200 bg-stone-50">{permissions.map((permission) => {
        const disabled = busy || (permission.id === "recordings" && !choices.transcript);
        return <label key={permission.id} className={`flex items-center justify-between gap-5 p-4 text-left transition-colors duration-200 ease-out ${disabled ? "cursor-not-allowed" : "cursor-grab hover:bg-stone-100 active:cursor-grabbing"}`}>
          <span className="min-w-0 flex-1 text-left"><span className="block text-left text-sm font-semibold text-stone-900">{permission.title}</span><span className="mt-1 block text-left text-xs leading-5 text-stone-500">{permission.detail}</span></span>
          <input
            type="checkbox"
            role="switch"
            aria-label={`Share ${permission.title.toLowerCase()} with client`}
            checked={choices[permission.id]}
            disabled={disabled}
            onChange={(event) => { const checked = event.currentTarget.checked; setChoices((value) => ({ ...value, [permission.id]: checked, ...(permission.id === "transcript" && !checked ? { recordings: false } : {}) })); setSaved(false); }}
            className="relative h-6 w-11 shrink-0 appearance-none rounded-full border border-stone-300 bg-stone-200 transition-colors duration-200 ease-out before:absolute before:left-0.5 before:top-0.5 before:size-4 before:rounded-full before:bg-white before:shadow-sm before:transition-transform before:duration-200 before:ease-out checked:border-emerald-700 checked:bg-emerald-800 checked:before:translate-x-5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 disabled:cursor-not-allowed disabled:opacity-50 motion-reduce:transition-none motion-reduce:before:transition-none"
          />
        </label>;
      })}</div>
    </div> : null}
    {section !== "scheduling" ? <div className="mt-6 flex justify-end border-t border-stone-200 pt-5"><button type="button" disabled={!canSave} onClick={() => void save()} className="cursor-grab rounded-lg bg-emerald-800 px-3.5 py-2 text-sm font-semibold text-white hover:bg-emerald-900 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing">{busy ? "Saving…" : "Save changes"}</button></div> : null}
    {error ? <p role="alert" className="mt-3 text-sm text-red-700">{error}</p> : null}
    {saved ? <p className="mt-3 text-right text-sm font-medium text-emerald-800" role="status">Client care settings saved.</p> : null}
    <audio ref={audioRef} className="sr-only" onTimeUpdate={(event) => { if (activeSample && event.currentTarget.currentTime >= activeSample.end) { event.currentTarget.pause(); setActiveSample(null); } }} onEnded={() => setActiveSample(null)} onError={() => { if (activeSample) { setError("The speaker sample is unavailable."); setActiveSample(null); } }} />
  </SettingsLayout>;
}
