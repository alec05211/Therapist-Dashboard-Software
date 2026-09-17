"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BriefEvidence, ClientInsights } from "@/lib/types";

type Props = { onViewEvidence: (evidence: BriefEvidence) => void };

function EvidenceLinks({ evidence, onViewEvidence }: { evidence: BriefEvidence[]; onViewEvidence: (evidence: BriefEvidence) => void }) {
  return <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1.5">
    {evidence.map((source) => {
      const label = source.session_label.replace("Synthetic · Elena Sadić · ", "");
      return <button key={source.evidence_id} type="button" onClick={() => onViewEvidence(source)} className="cursor-grab text-xs font-medium text-emerald-800 underline decoration-stone-400 underline-offset-3 transition duration-200 ease-out hover:text-emerald-950 hover:decoration-emerald-700 active:cursor-grabbing focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">{label}</button>;
    })}
  </div>;
}

function PatternCard({ pattern, onViewEvidence }: { pattern: ClientInsights["patterns"][number]; onViewEvidence: Props["onViewEvidence"] }) {
  return <article className="rounded-xl border border-stone-200 bg-stone-50 p-4">
    <div className="flex flex-wrap items-start justify-between gap-2"><h3 className="text-base font-semibold text-stone-900">{pattern.title}</h3><span className="rounded-full bg-emerald-50 px-2 py-1 text-[11px] font-medium text-emerald-900">{pattern.status}</span></div>
    <p className="mt-3 text-sm leading-6 text-stone-700">{pattern.summary}</p>
    <EvidenceLinks evidence={pattern.evidence} onViewEvidence={onViewEvidence} />
  </article>;
}

export function ClientInsights({ onViewEvidence }: Props) {
  const [insights, setInsights] = useState<ClientInsights | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [packetOpen, setPacketOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void api.getDemoClientInsights()
      .then((result) => { if (!cancelled) setInsights(result); })
      .catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load the clinical insights workspace."); });
    return () => { cancelled = true; };
  }, []);

  if (error) return <section className="rounded-2xl border border-stone-200 bg-white p-5 text-left shadow-sm"><h2 className="text-lg font-semibold text-stone-900">Clinical insights</h2><p className="mt-3 text-sm text-red-700">{error}</p></section>;
  if (!insights) return <section className="rounded-2xl border border-stone-200 bg-white p-5 text-left shadow-sm"><h2 className="text-lg font-semibold text-stone-900">Clinical insights</h2><p className="mt-3 text-sm text-stone-600">Preparing the longitudinal record…</p></section>;

  return <section className="text-left" aria-label="Clinical insights workspace">
    <header className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-sm font-medium text-emerald-800">Client insights</p><h2 className="mt-1 text-xl font-semibold tracking-tight text-stone-900">Longitudinal review</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-stone-600">A reviewable working record across completed sessions. Pattern language is intentionally provisional and linked to source material.</p></div><span className="rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-900">{insights.status}</span></div>
      <p className="mt-5 max-w-3xl border-l-2 border-emerald-300 pl-4 text-[15px] leading-7 text-stone-700">{insights.narrative}</p>
      <p className="mt-4 text-xs leading-5 text-stone-500">{insights.review_note}</p>
    </header>

    <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="grid gap-6">
        <section aria-labelledby="patterns-heading"><div className="mb-3 flex items-baseline justify-between gap-3"><h2 id="patterns-heading" className="text-base font-semibold text-stone-900">Possible patterns to review</h2><span className="text-xs text-stone-500">Source-grounded, not clinical conclusions</span></div><div className="grid gap-3">{insights.patterns.map((pattern) => <PatternCard key={pattern.id} pattern={pattern} onViewEvidence={onViewEvidence} />)}</div></section>
        <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm" aria-labelledby="threads-heading"><h2 id="threads-heading" className="text-base font-semibold text-stone-900">Questions to keep open</h2><p className="mt-1 text-sm leading-6 text-stone-600">These are unresolved, source-linked threads—not instructions for the next session.</p><ol className="mt-4 grid gap-4">{insights.open_threads.map((thread, index) => <li key={thread.text} className="border-t border-stone-200 pt-4 first:border-t-0 first:pt-0"><div className="flex gap-3"><span className="grid size-6 shrink-0 place-items-center rounded-full bg-stone-100 text-xs font-semibold text-stone-600">{index + 1}</span><div><p className="text-sm leading-6 text-stone-800">{thread.text}</p><EvidenceLinks evidence={thread.evidence} onViewEvidence={onViewEvidence} /></div></div></li>)}</ol></section>
      </div>

      <aside className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm" aria-label="Pre-session context packet">
        <p className="text-sm font-medium text-emerald-800">Brief context packet</p><h2 className="mt-1 text-base font-semibold text-stone-900">What the brief receives</h2><p className="mt-2 text-sm leading-6 text-stone-600">{insights.context_packet.purpose}</p><p className="mt-3 text-xs leading-5 text-stone-500">{insights.context_packet.selection_policy}</p>
        <button type="button" onClick={() => setPacketOpen((open) => !open)} className="mt-4 cursor-grab text-sm font-medium text-emerald-800 underline underline-offset-3 transition hover:text-emerald-950 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700" aria-expanded={packetOpen}>{packetOpen ? "Hide packet contents" : `Review ${insights.context_packet.items.length} selected items`}</button>
        {packetOpen ? <div className="mt-4 grid gap-4 border-t border-stone-200 pt-4">{insights.context_packet.items.map((item) => <article key={`${item.kind}-${item.text}`}><p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-stone-500">{item.kind}</p><p className="mt-1 text-sm leading-6 text-stone-700">{item.text}</p><EvidenceLinks evidence={item.evidence} onViewEvidence={onViewEvidence} /></article>)}</div> : null}
        <div className="mt-5 border-t border-stone-200 pt-4"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-stone-500">Record coverage</p><ul className="mt-3 grid gap-2">{insights.records.map((record) => <li key={record.session_id} className="text-xs leading-5 text-stone-600"><span className="font-medium text-stone-700">{record.session_label.replace("Synthetic · Elena Sadić · ", "")}</span><br />{record.note_status}</li>)}</ul></div>
      </aside>
    </div>
  </section>;
}
