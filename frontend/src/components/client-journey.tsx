"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { JOURNEY_CATEGORIES } from "@/lib/journey-categories";
import type { BriefEvidence, ClientJourneyEntry, LongitudinalRecordContext } from "@/lib/types";

type Props = {
  recordContext: LongitudinalRecordContext;
  onViewEvidence: (source: BriefEvidence) => void;
};

const formatTime = (seconds?: number) => {
  const safeSeconds = Number.isFinite(seconds) ? Number(seconds) : 0;
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = Math.floor(safeSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainder}`;
};

const evidenceSessionLabel = (label: string) => {
  const parts = label.split(" · ");
  return parts[0] === "Synthetic" && parts.length > 2 ? parts.slice(2).join(" · ") : label;
};

function AcceptedEvidenceCard({ entry, recordContext, onViewEvidence, onSaved }: {
  entry: ClientJourneyEntry;
  recordContext: LongitudinalRecordContext;
  onViewEvidence: Props["onViewEvidence"];
  onSaved: () => Promise<void>;
}) {
  const [saving, setSaving] = useState<"stale" | "hidden" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const save = async (status: "stale" | "hidden") => {
    setSaving(status);
    setError(null);
    try {
      await api.reviewClientJourneyEntry(
        recordContext.organizationId,
        recordContext.clientId,
        entry.id,
        { category: entry.categories[0], categories: entry.categories, text: entry.text, status },
      );
      await onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update this accepted claim.");
    } finally {
      setSaving(null);
    }
  };

  return <article className="rounded-xl border border-stone-300 bg-stone-50 p-4">
    <p className="text-sm leading-6 text-stone-800">{entry.text}</p>
    <div className="mt-3 flex flex-wrap gap-2">
      {entry.evidence.map((source, index) => <button
        key={source.evidence_id}
        type="button"
        onClick={() => onViewEvidence(source)}
        className="cursor-grab rounded-lg border border-stone-300 bg-white px-2.5 py-1.5 text-left text-xs font-medium text-emerald-800 transition-colors hover:bg-stone-100 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"
      >
        {entry.evidence.length > 1 ? `Source ${index + 1} · ` : ""}{evidenceSessionLabel(source.session_label)} · {formatTime(source.start)}
      </button>)}
    </div>
    <div className="mt-4 flex flex-wrap justify-end gap-2">
      <button type="button" disabled={Boolean(saving)} onClick={() => void save("stale")} className="cursor-grab rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-xs font-medium text-stone-700 active:cursor-grabbing disabled:cursor-wait disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">
        {saving === "stale" ? "Updating…" : "Mark outdated"}
      </button>
      <button type="button" disabled={Boolean(saving)} onClick={() => void save("hidden")} className="cursor-grab rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-xs font-medium text-stone-700 active:cursor-grabbing disabled:cursor-wait disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">
        {saving === "hidden" ? "Hiding…" : "Hide"}
      </button>
    </div>
    {error ? <p role="alert" className="mt-3 text-xs text-red-700">{error}</p> : null}
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
      .then((result) => {
        if (!cancelled) {
          setEntries(result.entries);
          setError(null);
        }
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load accepted evidence.");
      });
    return () => { cancelled = true; };
  }, [recordContext.organizationId, recordContext.clientId]);

  const accepted = entries?.filter((entry) => entry.status === "accepted" && entry.evidence.length > 0) ?? [];
  const groupedClaims = JOURNEY_CATEGORIES.map((category) => ({
    ...category,
    entries: accepted.filter((entry) => entry.categories.includes(category.value)),
  })).filter((group) => group.entries.length > 0);

  return <section className="mt-6 rounded-2xl border border-stone-300 bg-white p-5 text-left shadow-sm" aria-label="Accepted evidence claims">
    <h2 className="text-lg font-semibold text-stone-900">Evidence and review</h2>
    <p className="mt-1 text-xs leading-5 text-stone-500">Therapist-accepted claims from transcript review, grouped by how they should inform future synthesis.</p>
    {error ? <p role="alert" className="mt-4 text-sm text-red-700">{error}</p> : !entries ? <p className="mt-4 text-sm text-stone-600">Loading accepted evidence…</p> : groupedClaims.length ? <div className="mt-5 grid gap-3">
      {groupedClaims.map((group) => <details key={group.value} className="group rounded-xl border border-stone-300 bg-white">
        <summary className="flex cursor-grab list-none items-center justify-between gap-4 rounded-xl px-4 py-3 text-sm font-semibold text-stone-900 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 [&::-webkit-details-marker]:hidden">
          <span>{group.label}</span>
          <span className="flex items-center gap-3">
            <span className="text-xs font-medium tabular-nums text-stone-500">{group.entries.length}</span>
            <svg viewBox="0 0 20 20" className="size-4 text-stone-500 transition-transform group-open:rotate-180" fill="none" aria-hidden="true"><path d="m5.5 7.5 4.5 4.5 4.5-4.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </span>
        </summary>
        <div className="grid gap-3 border-t border-stone-200 p-3">
          {group.entries.map((entry) => <AcceptedEvidenceCard key={entry.id} entry={entry} recordContext={recordContext} onViewEvidence={onViewEvidence} onSaved={load} />)}
        </div>
      </details>)}
    </div> : <p className="mt-4 rounded-xl border border-stone-300 bg-stone-50 p-4 text-sm leading-6 text-stone-600">No accepted evidence yet. Capture an insight while reviewing a suggested passage in a completed transcript.</p>}
  </section>;
}
