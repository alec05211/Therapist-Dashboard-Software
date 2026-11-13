"use client";

import { useEffect, useState } from "react";

export function VoiceProfileSettings() {
  const [profile, setProfile] = useState<{ available: boolean; enrolled: boolean }>();
  const [sample, setSample] = useState<File>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    void fetch("/api/account/voice-profile").then(async (response) => {
      if (!response.ok) throw new Error();
      setProfile(await response.json());
    }).catch(() => setError("Voice profile could not be loaded."));
  }, []);

  async function update(remove: boolean) {
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      if (sample) body.append("audio", sample);
      const response = await fetch("/api/account/voice-profile", {
        method: remove ? "DELETE" : "PUT",
        body: remove ? undefined : body,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Voice profile could not be saved.");
      setProfile((current) => current && { ...current, enrolled: result.enrolled });
      setSample(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Voice profile could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  const button = "cursor-grab rounded-lg border border-stone-300 px-3 py-2 active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-60";
  return <div className="mt-6 space-y-3 rounded-xl border border-stone-200 p-4 text-sm">
    <p>Enroll a short recording of only your voice to let the dashboard automatically identify you in future session transcripts.</p>
    {profile && <p role="status">{profile.enrolled ? "Voice profile enrolled." : profile.available ? "No voice profile enrolled." : "Voice enrollment is unavailable."}</p>}
    {profile?.available && <form onSubmit={(event) => { event.preventDefault(); void update(false); }} className="flex flex-wrap items-end gap-3">
      <label className="grid gap-1">Voice recording
        <input key={profile.enrolled ? "enrolled" : "empty"} type="file" accept="audio/*,video/webm" capture disabled={busy} onChange={(event) => setSample(event.target.files?.[0])} />
      </label>
      <button type="submit" className={button} disabled={busy || !sample}>{profile.enrolled ? "Replace voice profile" : "Enroll voice"}</button>
    </form>}
    {profile?.enrolled && <button type="button" className={button} disabled={busy} onClick={() => void update(true)}>Delete voice profile</button>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
  </div>;
}
