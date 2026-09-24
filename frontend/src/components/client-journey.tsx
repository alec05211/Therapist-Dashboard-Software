"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BriefEvidence, ClientJourneyEntry, LongitudinalRecordContext } from "@/lib/types";

type Props = { recordContext: LongitudinalRecordContext; onViewEvidence: (source: BriefEvidence) => void };
type Category = ClientJourneyEntry["category"];

const categories: Array<{ value: Category; label: string }> = [
  { value: "context", label: "Client context" },
  { value: "theme", label: "Theme" },
  { value: "important_quote", label: "Important statement" },
  { value: "resolution", label: "Resolution" },
  { value: "breakthrough", label: "Breakthrough" },
  { value: "open_thread", label: "Open thread" },
];

function JourneyCard({ entry, recordContext, onViewEvidence, onSaved }: {
  entry: ClientJourneyEntry; recordContext: LongitudinalRecordContext;
  onViewEvidence: Props["onViewEvidence"]; onSaved: () => Promise<void>;
}) {
  const [text, setText] = useState(entry.text);
  const [category, setCategory] = useState<Category>(entry.category);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const proposed = entry.status === "proposed";
  const save = async (status: "accepted" | "rejected" | "hidden" | "stale") => {
    setSaving(true); setError(null);
    try {
      await api.reviewClientJourneyEntry(recordContext.organizationId, recordContext.clientId, entry.id,
        { category, text: text.trim(), status });
      await onSaved();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save the review decision."); }
    finally { setSaving(false); }
  };
  return <article className="rounded-xl border border-stone-300 bg-stone-50 p-4">
    <div className="flex items-start justify-between gap-3"><span className="text-xs font-medium capitalize text-stone-600">{entry.status}</span><span className="text-xs text-stone-500">{entry.evidence.length} cited {entry.evidence.length === 1 ? "passage" : "passages"}</span></div>
    {proposed ? <div className="mt-3 grid gap-3">
      <label className="grid gap-1 text-xs font-medium text-stone-600">Category<select value={category} onChange={event => setCategory(event.target.value as Category)} className="rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 focus:outline-none focus-visible:border-emerald-700">{categories.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
      <label className="grid gap-1 text-xs font-medium text-stone-600">Proposed entry<textarea value={text} onChange={event => setText(event.target.value)} rows={3} maxLength={4000} className="w-full resize-y rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm leading-6 text-stone-900 focus:outline-none focus-visible:border-emerald-700" /></label>
    </div> : <p className="mt-3 text-sm leading-6 text-stone-800">{entry.text}</p>}
    {entry.evidence[0] && <button type="button" onClick={() => onViewEvidence(entry.evidence[0])} className="mt-3 cursor-grab text-xs font-medium text-emerald-800 underline underline-offset-3 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Review cited transcript</button>}
    <div className="mt-4 flex flex-wrap gap-2">
      {proposed ? <><button type="button" disabled={saving || !text.trim()} onClick={() => void save("accepted")} className="cursor-grab rounded-xl bg-emerald-800 px-3 py-2 text-xs font-semibold text-white active:cursor-grabbing disabled:cursor-wait disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Accept for brief</button><button type="button" disabled={saving} onClick={() => void save("rejected")} className="cursor-grab rounded-xl border border-stone-300 px-3 py-2 text-xs font-medium text-stone-700 active:cursor-grabbing disabled:cursor-wait focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Dismiss</button></> : entry.status === "accepted" ? <><button type="button" disabled={saving} onClick={() => void save("stale")} className="cursor-grab rounded-xl border border-stone-300 px-3 py-2 text-xs font-medium text-stone-700 active:cursor-grabbing disabled:cursor-wait focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Mark outdated</button><button type="button" disabled={saving} onClick={() => void save("hidden")} className="cursor-grab rounded-xl border border-stone-300 px-3 py-2 text-xs font-medium text-stone-700 active:cursor-grabbing disabled:cursor-wait focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Hide</button></> : null}
    </div>
    {error && <p role="alert" className="mt-3 text-xs text-red-700">{error}</p>}
  </article>;
}

export function ClientJourney({ recordContext, onViewEvidence }: Props) {
  const [entries, setEntries] = useState<ClientJourneyEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = async () => {
    const result = await api.getClientJourney(recordContext.organizationId, recordContext.clientId);
    setEntries(result.entries);
  };
  useEffect(() => {
    let cancelled = false;
    void api.getClientJourney(recordContext.organizationId, recordContext.clientId)
      .then(result => { if (!cancelled) setEntries(result.entries); })
      .catch(reason => { if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load client journey entries."); });
    return () => { cancelled = true; };
  }, [recordContext.organizationId, recordContext.clientId]);
  const proposed = entries?.filter(entry => entry.status === "proposed") ?? [];
  const accepted = entries?.filter(entry => entry.status === "accepted") ?? [];
  const quotes = accepted.filter(entry => entry.category === "important_quote");
  const history = accepted.filter(entry => entry.category !== "important_quote");
  return <section className="mt-6 rounded-2xl border border-stone-300 bg-white p-5 text-left shadow-sm" aria-label="Client journey review">
    <h2 className="text-lg font-semibold text-stone-900">Client journey</h2>
    {error ? <p role="alert" className="mt-4 text-sm text-red-700">{error}</p> : !entries ? <p className="mt-4 text-sm text-stone-600">Loading journey entries…</p> : <div className="mt-5 grid gap-6">
      <details className="rounded-xl border border-stone-300 bg-stone-50 p-4">
        <summary className="cursor-grab text-sm font-semibold text-stone-900 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-emerald-700">Saved quotes · {quotes.length}</summary>
        {quotes.length ? <div className="mt-4 grid gap-4">{quotes.map(entry => <article key={entry.id}>
          {entry.evidence.map(source => <button key={source.evidence_id} type="button" onClick={() => onViewEvidence(source)} className="mb-2 block cursor-grab text-left text-sm leading-6 text-stone-800 underline decoration-stone-400 underline-offset-4 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-emerald-700">“{source.quote}” <span className="text-xs text-stone-500">{source.session_label}</span></button>)}
          <JourneyCard entry={entry} recordContext={recordContext} onViewEvidence={onViewEvidence} onSaved={load} />
        </article>)}</div> : <p className="mt-3 text-sm text-stone-600">Review an underlined passage in a completed transcript to save an important statement.</p>}
      </details>
      <details className="rounded-xl border border-stone-300 p-4"><summary className="cursor-grab text-sm font-semibold text-stone-900 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-emerald-700">Other proposals · {proposed.length}</summary>{proposed.length ? <div className="mt-3 grid gap-3">{proposed.map(entry => <JourneyCard key={entry.id} entry={entry} recordContext={recordContext} onViewEvidence={onViewEvidence} onSaved={load} />)}</div> : <p className="mt-2 text-sm text-stone-600">No passages await review.</p>}</details>
      <details className="rounded-xl border border-stone-300 p-4"><summary className="cursor-grab text-sm font-semibold text-stone-900 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-emerald-700">Accepted history · {history.length}</summary>{history.length ? <div className="mt-3 grid gap-3">{history.map(entry => <JourneyCard key={entry.id} entry={entry} recordContext={recordContext} onViewEvidence={onViewEvidence} onSaved={load} />)}</div> : <p className="mt-2 text-sm text-stone-600">Accepted entries will inform the pre-session brief.</p>}</details>
    </div>}
  </section>;
}
