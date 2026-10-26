"use client";

import { useEffect, useState } from "react";

type Event = { id: string; timestamp: string; message: string; level: "info" | "warning" | "error"; details: Record<string, number | string> };
type Timeline = { events: Event[]; checked_at: string; retention_days: number; summary: { status: string; desired_revision: number; published_revision: number; attempt_count: number; error: string | null } };

function timestamp(value: string) {
  return new Date(value).toLocaleString(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false, timeZoneName: "short" });
}

export function ClientDiagnostics({ clientId }: { clientId?: string }) {
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (!clientId || paused) return;
    let active = true;
    let controller: AbortController | null = null;
    const load = async () => {
      if (document.visibilityState === "hidden") return;
      controller?.abort();
      controller = new AbortController();
      try {
        const response = await fetch(`/api/client-diagnostics?client_id=${encodeURIComponent(clientId)}`, { cache: "no-store", signal: controller.signal });
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail || "Could not load client diagnostics.");
        if (active) { setTimeline(body as Timeline); setError(null); }
      } catch (reason) {
        if (active && !(reason instanceof DOMException && reason.name === "AbortError")) setError(reason instanceof Error ? reason.message : "Could not load client diagnostics.");
      }
    };
    void load();
    const timer = paused ? null : window.setInterval(() => void load(), 10_000);
    const onVisible = () => { if (!paused) void load(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => { active = false; controller?.abort(); if (timer) window.clearInterval(timer); document.removeEventListener("visibilitychange", onVisible); };
  }, [clientId, paused]);

  if (!clientId) return <p role="alert" className="mt-5 text-sm text-red-700">Open diagnostics from a client workspace.</p>;

  return <section className="mt-4 text-left" aria-label="Client diagnostics">
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div className="text-sm text-stone-600">{timeline ? <>Insights: <span className="font-semibold text-stone-900">{timeline.summary.status}</span><span className="mx-2" aria-hidden="true">·</span>Published {timeline.summary.published_revision} / queued {timeline.summary.desired_revision}<span className="mx-2" aria-hidden="true">·</span>Attempt {timeline.summary.attempt_count}</> : "Connecting to event log…"}</div>
      <button type="button" aria-pressed={paused} onClick={() => setPaused(value => !value)} className="cursor-grab rounded-lg border border-stone-300 bg-stone-50 px-3 py-1.5 text-xs font-semibold text-stone-800 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing">{paused ? "Resume live log" : "Pause live log"}</button>
    </div>
    {error ? <p role="alert" className="mb-3 text-sm text-red-700">{error}</p> : null}
    <div className="overflow-hidden rounded-xl border border-[#44403c] bg-[#171b19] text-[#d6e4dc] shadow-inner">
      <div className="flex items-center justify-between gap-3 border-b border-[#37433c] px-4 py-3 font-mono text-xs text-[#a4b9ac]"><span>client / events</span><span>{paused ? "PAUSED" : "LIVE · 10s"}</span></div>
      <div role="log" aria-label="Timestamped client events, newest first" aria-live="off" tabIndex={0} className="max-h-[32rem] min-h-64 overflow-auto px-4 py-3 font-mono text-xs leading-6 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-emerald-400">
        {!timeline ? <p role="status">{error ? "Event log unavailable." : "Loading events…"}</p> : timeline.events.length === 0 ? <p>No recorded events for this client yet.</p> : timeline.events.map(event => <div key={event.id} className="grid grid-cols-[minmax(10rem,12rem)_minmax(0,1fr)] gap-4 border-b border-[#29372f] py-2 last:border-0">
          <time dateTime={event.timestamp} className="text-[#94aa9b]">{timestamp(event.timestamp)}</time>
          <div className="min-w-0 break-words"><span className={event.level === "error" ? "text-[#ffb3a7]" : event.level === "warning" ? "text-[#efd39a]" : "text-[#d6e4dc]"}>[{event.level.toUpperCase()}] {event.message}</span>{Object.keys(event.details).length ? <div className="break-all text-[#94aa9b]">{Object.entries(event.details).map(([key, value]) => `${key}=${value}`).join("  ")}</div> : null}</div>
        </div>)}
      </div>
    </div>
    <p className="mt-3 text-xs leading-5 text-stone-500">{timeline ? `Checked ${timestamp(timeline.checked_at)}. ` : ""}Newest 200 events. Worker stage logs cover the last 30 days; earlier attempts may show only their last status. Clinical content is excluded.</p>
  </section>;
}
