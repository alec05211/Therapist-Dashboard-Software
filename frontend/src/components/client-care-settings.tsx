"use client";

import { useState } from "react";
import { chooseSessionCadence } from "@/lib/workspace-preferences";

type ClientCareSettingsProps = {
  onReturnToWorkspace: () => void;
};

export function ClientCareSettings({ onReturnToWorkspace }: ClientCareSettingsProps) {
  const [preferredName, setPreferredName] = useState("");
  const [canViewSummaries, setCanViewSummaries] = useState(false);
  const [sessionCadence, setSessionCadence] = useState("Thursdays · 3:00 PM · 50 minutes");
  const [saved, setSaved] = useState(false);

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-5 text-left shadow-sm sm:p-7" aria-labelledby="client-care-settings-title">
      <div className="flex items-start justify-between gap-5">
        <div>
          <p className="text-sm font-medium text-emerald-800">Elena Sadić · Client settings</p>
          <h2 id="client-care-settings-title" className="mt-1 text-xl font-semibold tracking-tight text-stone-900">Client care settings</h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-stone-600">Relationship-specific preferences, access, and care coordination. These are separate from your personal account settings and from controls on an individual session.</p>
        </div>
      </div>

      <div className="mt-6 grid gap-4">
              <fieldset className="rounded-xl border border-stone-200 p-4">
                <legend className="px-1 text-sm font-semibold text-stone-900">How this client is identified</legend>
                <label className="mt-3 block text-sm font-medium text-stone-700" htmlFor="preferred-name">Preferred name</label>
                <input id="preferred-name" value={preferredName} onChange={(event) => setPreferredName(event.target.value)} placeholder="Name used in this workspace" className="mt-1.5 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-900 outline-none placeholder:text-stone-400 focus:border-emerald-700 focus:ring-2 focus:ring-emerald-100" />
                <p className="mt-2 text-xs leading-5 text-stone-500">This will eventually be distinct from the legal name stored in the client record.</p>
              </fieldset>

              <fieldset className="rounded-xl border border-stone-200 p-4" id="scheduling">
                <legend className="px-1 text-sm font-semibold text-stone-900">Scheduling</legend>
                <label className="mt-3 block text-sm font-medium text-stone-700" htmlFor="session-cadence">Usual session pattern</label>
                <select id="session-cadence" value={sessionCadence} onChange={(event) => setSessionCadence(event.target.value)} className="mt-1.5 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 outline-none focus:border-emerald-700 focus:ring-2 focus:ring-emerald-100">
                  <option>Thursdays · 3:00 PM · 50 minutes</option>
                  <option>Tuesdays · 10:00 AM · 50 minutes</option>
                  <option>Every other Monday · 4:00 PM · 50 minutes</option>
                </select>
                <p className="mt-2 text-xs leading-5 text-stone-500">This is a display preference for the session cards only. It does not create appointments or scheduling availability yet.</p>
              </fieldset>

              <fieldset className="rounded-xl border border-stone-200 p-4">
                <legend className="px-1 text-sm font-semibold text-stone-900">Client access</legend>
                <label className="mt-3 flex cursor-pointer items-start gap-3">
                  <input type="checkbox" checked={canViewSummaries} onChange={(event) => setCanViewSummaries(event.target.checked)} className="mt-0.5 size-4 accent-emerald-700" />
                  <span><span className="block text-sm font-medium text-stone-800">Allow client access to therapist-approved summaries</span><span className="mt-1 block text-xs leading-5 text-stone-500">Individual sessions still require review and explicit sharing before anything is visible to a client.</span></span>
                </label>
              </fieldset>

              <div className="rounded-xl border border-stone-200 p-4">
                <h2 className="text-sm font-semibold text-stone-900">Speaker identity</h2>
                <p className="mt-2 text-sm leading-6 text-stone-600">Speaker names and labels will be managed here in a future update, rather than from an individual completed-session review.</p>
                <p className="mt-2 text-xs font-medium text-stone-500">Not configured yet</p>
              </div>

              <div className="rounded-xl border border-stone-200 p-4">
                <h2 className="text-sm font-semibold text-stone-900">Care coordination</h2>
                <p className="mt-2 text-sm leading-6 text-stone-600">Therapist handoff, care-team access, consent, and retention controls will live here as those workflows are introduced.</p>
                <p className="mt-2 text-xs font-medium text-stone-500">Not configured yet</p>
              </div>
      </div>

      <div className="mt-6 flex items-center justify-between gap-4 border-t border-stone-200 pt-5">
        <p className="text-xs text-stone-500">Initial UI only — saving is local to this browser session.</p>
        <div className="flex gap-3">
          <button type="button" onClick={onReturnToWorkspace} className="cursor-grab rounded-lg px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing">Return to workspace</button>
          <button type="button" onClick={() => { chooseSessionCadence(sessionCadence); setSaved(true); }} className="cursor-grab rounded-lg bg-emerald-800 px-3.5 py-2 text-sm font-semibold text-white hover:bg-emerald-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing">Save changes</button>
        </div>
      </div>
      {saved ? <p className="mt-3 text-right text-sm font-medium text-emerald-800" role="status">Changes saved for this browser session.</p> : null}
    </section>
  );
}
