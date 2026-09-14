"use client";

import { useState } from "react";

export function ClientCareSettings() {
  const [isOpen, setIsOpen] = useState(false);
  const [preferredName, setPreferredName] = useState("");
  const [canViewSummaries, setCanViewSummaries] = useState(false);
  const [saved, setSaved] = useState(false);

  const close = () => {
    setIsOpen(false);
    setSaved(false);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="inline-flex items-center gap-2 rounded-lg border border-stone-300 bg-white px-3.5 py-2 text-sm font-semibold text-stone-700 shadow-sm hover:bg-stone-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"
      >
        <span aria-hidden="true">⚙</span>
        Client care settings
      </button>

      {isOpen ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-stone-950/30 p-4 sm:items-center" role="presentation" onMouseDown={close}>
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="client-care-settings-title"
            className="max-h-[min(760px,calc(100vh-2rem))] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl sm:p-7"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-5">
              <div>
                <p className="text-sm font-medium text-emerald-800">Client workspace</p>
                <h1 id="client-care-settings-title" className="mt-1 text-xl font-semibold tracking-tight text-stone-900">Client care settings</h1>
                <p className="mt-2 max-w-xl text-sm leading-6 text-stone-600">Relationship-specific preferences, access, and care coordination. These are separate from your personal account settings and from controls on an individual session.</p>
              </div>
              <button type="button" onClick={close} className="rounded-md p-2 text-stone-500 hover:bg-stone-100 hover:text-stone-900 focus-visible:outline-2 focus-visible:outline-emerald-700" aria-label="Close client care settings">×</button>
            </div>

            <div className="mt-6 grid gap-4">
              <fieldset className="rounded-xl border border-stone-200 p-4">
                <legend className="px-1 text-sm font-semibold text-stone-900">How this client is identified</legend>
                <label className="mt-3 block text-sm font-medium text-stone-700" htmlFor="preferred-name">Preferred name</label>
                <input id="preferred-name" value={preferredName} onChange={(event) => setPreferredName(event.target.value)} placeholder="Name used in this workspace" className="mt-1.5 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-900 outline-none placeholder:text-stone-400 focus:border-emerald-700 focus:ring-2 focus:ring-emerald-100" />
                <p className="mt-2 text-xs leading-5 text-stone-500">This will eventually be distinct from the legal name stored in the client record.</p>
              </fieldset>

              <fieldset className="rounded-xl border border-stone-200 p-4">
                <legend className="px-1 text-sm font-semibold text-stone-900">Client access</legend>
                <label className="mt-3 flex cursor-pointer items-start gap-3">
                  <input type="checkbox" checked={canViewSummaries} onChange={(event) => setCanViewSummaries(event.target.checked)} className="mt-0.5 size-4 accent-emerald-700" />
                  <span><span className="block text-sm font-medium text-stone-800">Allow client access to therapist-approved summaries</span><span className="mt-1 block text-xs leading-5 text-stone-500">Individual sessions still require review and explicit sharing before anything is visible to a client.</span></span>
                </label>
              </fieldset>

              <div className="rounded-xl border border-stone-200 p-4">
                <h2 className="text-sm font-semibold text-stone-900">Care coordination</h2>
                <p className="mt-2 text-sm leading-6 text-stone-600">Therapist handoff, care-team access, consent, and retention controls will live here as those workflows are introduced.</p>
                <p className="mt-2 text-xs font-medium text-stone-500">Not configured yet</p>
              </div>
            </div>

            <div className="mt-6 flex items-center justify-between gap-4 border-t border-stone-200 pt-5">
              <p className="text-xs text-stone-500">Initial UI only — saving is local to this browser session.</p>
              <div className="flex gap-3">
                <button type="button" onClick={close} className="rounded-lg px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-100">Cancel</button>
                <button type="button" onClick={() => setSaved(true)} className="rounded-lg bg-emerald-800 px-3.5 py-2 text-sm font-semibold text-white hover:bg-emerald-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Save changes</button>
              </div>
            </div>
            {saved ? <p className="mt-3 text-right text-sm font-medium text-emerald-800" role="status">Changes saved for this browser session.</p> : null}
          </section>
        </div>
      ) : null}
    </>
  );
}
