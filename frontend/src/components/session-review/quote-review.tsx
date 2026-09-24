"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ClientJourneyEntry, LongitudinalRecordContext } from "@/lib/types";

export function useQuoteProposals(context?: LongitudinalRecordContext, sessionId?: string) {
  const [result, setResult] = useState<{ key: string; entries: ClientJourneyEntry[] }>({ key: "", entries: [] });
  const [error, setError] = useState<{ key: string; message: string } | null>(null);
  const organizationId = context?.organizationId;
  const clientId = context?.clientId;
  const key = `${organizationId}/${clientId}/${sessionId}`;
  useEffect(() => {
    if (!organizationId || !clientId || !sessionId) return;
    let cancelled = false;
    void api.getClientJourney(organizationId, clientId).then(({ entries }) => {
      if (!cancelled) setResult({ key, entries: entries.filter(entry => entry.session_id === sessionId) });
    }).catch(reason => {
      if (!cancelled) setError({ key, message: reason instanceof Error ? reason.message : "Could not load suggested passages." });
    });
    return () => { cancelled = true; };
  }, [organizationId, clientId, sessionId, key]);
  return {
    entries: result.key === key ? result.entries.filter(entry => entry.status === "proposed" || entry.status === "accepted") : [],
    error: error?.key === key ? error.message : null,
    onSaved: (updated: ClientJourneyEntry) => setResult(previous => ({ ...previous, entries: previous.entries.map(entry => entry.id === updated.id ? updated : entry) })),
  };
}

const control = "cursor-grab rounded-xl border border-stone-300 px-3 py-2 text-xs font-semibold active:cursor-grabbing disabled:cursor-wait disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700";

export function QuoteReview({ entry, recordContext, onSaved }: {
  entry: ClientJourneyEntry;
  recordContext: LongitudinalRecordContext;
  onSaved: (entry: ClientJourneyEntry) => void;
}) {
  const [text, setText] = useState(entry.text);
  const [category, setCategory] = useState<ClientJourneyEntry["category"]>(entry.status === "proposed" ? "important_quote" : entry.category);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const save = async (status: "accepted" | "rejected" | "stale") => {
    setSaving(true); setError(null); setSaved(false);
    try {
      await api.reviewClientJourneyEntry(recordContext.organizationId, recordContext.clientId, entry.id, { category, text: text.trim(), status });
      onSaved({ ...entry, category, text: text.trim(), status });
      setSaved(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save quote guidance."); }
    finally { setSaving(false); }
  };
  return <div className="my-3 rounded-xl border border-stone-300 bg-white p-4 text-left">
    <h4 className="text-sm font-semibold text-stone-900">{entry.status === "proposed" ? "Suggested passage · review" : "Saved passage"}</h4>
    <p className="mt-2 text-xs leading-5 text-stone-600">Your interpretation is saved with the original transcript evidence. Accepted guidance informs the brief; it does not regenerate insights.</p>
    <label className="mt-3 grid gap-1 text-xs font-medium text-stone-700">What should future synthesis focus on?
      <textarea value={text} onChange={event => { setText(event.target.value); setSaved(false); }} maxLength={4000} rows={3} disabled={saving} className="resize-y rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 text-sm leading-6 text-stone-900 focus:outline-none focus-visible:border-emerald-700" />
    </label>
    <label className="mt-3 grid gap-1 text-xs font-medium text-stone-700">Use as
      <select value={category} onChange={event => { setCategory(event.target.value as ClientJourneyEntry["category"]); setSaved(false); }} disabled={saving} className="cursor-grab rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 text-sm text-stone-900 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-emerald-700">
        <option value="important_quote">Important statement</option><option value="open_thread">Follow-up for next session</option><option value="theme">Theme to consider</option><option value="context">Relevant context</option><option value="breakthrough">Breakthrough</option><option value="resolution">Resolution</option>
      </select>
    </label>
    <div className="mt-3 flex flex-wrap gap-2">
      <button type="button" disabled={saving || !text.trim()} onClick={() => void save("accepted")} className={`${control} bg-emerald-800 text-white`}>{saving ? "Saving…" : "Save for brief"}</button>
      <button type="button" disabled={saving || !text.trim()} onClick={() => void save(entry.status === "proposed" ? "rejected" : "stale")} className={`${control} text-stone-700`}>{entry.status === "proposed" ? "Dismiss suggestion" : "Mark outdated"}</button>
    </div>
    {saved && <p role="status" className="mt-3 text-xs text-emerald-800">Saved for future briefs.</p>}
    {error && <p role="alert" className="mt-3 text-xs text-red-700">{error}</p>}
  </div>;
}
