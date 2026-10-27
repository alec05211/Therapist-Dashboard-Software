"use client";

import { useEffect, useRef, useState } from "react";

type Event = { id: string; timestamp: string; message: string; level: "info" | "warning" | "error"; details: Record<string, number | string> };
type Timeline = { events: Event[]; checked_at: string; retention_days: number; summary: { status: string; desired_revision: number; published_revision: number; queued_event_count: number; attempt_count: number; error: string | null } };

function timestamp(value: string) {
  return new Date(value).toLocaleString(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false, timeZoneName: "short" });
}

function DiagnosticRow({ event }: { event: Event }) {
  const details = Object.entries(event.details);
  const detailLabels: Record<string, string> = {
    revision: "Insights revision", attempt: "Worker attempt", stage: "Processing stage",
    source_count: "Source records", context_bytes: "Context size (bytes)",
    request_bytes: "Request size (bytes)", input_tokens: "Input tokens", output_tokens: "Output tokens",
    repair_attempt: "Validation repair attempt", violation_count: "Validation issues", error_code: "Error code",
  };
  const description = [
    `${event.level.toUpperCase()}: ${event.message}`,
    new Date(event.timestamp).toLocaleString(undefined, { dateStyle: "full", timeStyle: "long" }),
    ...details.map(([key, value]) => `${detailLabels[key] ?? key.replaceAll("_", " ")}: ${value}`),
  ].join("\n");

  return <div role="group" tabIndex={0} title={description} aria-label={description} className="block w-full cursor-text rounded-sm py-0.5 text-left hover:bg-[#223029] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-emerald-400">
    <time dateTime={event.timestamp} className="mr-2 whitespace-nowrap text-[#94aa9b]">{timestamp(event.timestamp)}</time>
    <span className={`break-words ${event.level === "error" ? "text-[#ffb3a7]" : event.level === "warning" ? "text-[#efd39a]" : "text-[#d6e4dc]"}`}>[{event.level.toUpperCase()}] {event.message}</span>
    {details.length > 0 && <span className="ml-2 break-words text-[#94aa9b]">{details.map(([key, value]) => `${key}=${value}`).join(" ")}</span>}
  </div>;
}

export function ClientDiagnostics({ clientId }: { clientId?: string }) {
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const viewport = useRef<HTMLDivElement>(null);
  const followLatest = useRef(true);
  const [following, setFollowing] = useState(true);
  useEffect(() => {
    if (followLatest.current && viewport.current) {
      viewport.current.scrollTop = viewport.current.scrollHeight;
    }
  }, [timeline]);

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
      {timeline ? <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-stone-600">
        <span>Insights: <span className="font-semibold text-stone-900">{timeline.summary.status}</span></span>
        <dl className="flex flex-wrap gap-x-5 gap-y-2">
          <div className="flex gap-2"><dt>Queued changes</dt><dd className="font-mono font-semibold tabular-nums text-stone-900">{timeline.summary.queued_event_count}</dd></div>
          <div className="flex gap-2" title="Latest processed Insights revision. This cumulative version number does not reset."><dt>Published revision</dt><dd className="font-mono tabular-nums text-stone-900">{timeline.summary.published_revision}</dd></div>
          <div className="flex gap-2"><dt>Attempt</dt><dd className="font-mono tabular-nums text-stone-900">{timeline.summary.attempt_count}</dd></div>
        </dl>
      </div> : <p className="text-sm text-stone-600">Connecting to event log…</p>}
      <button type="button" aria-pressed={paused} onClick={() => setPaused(value => !value)} className="cursor-grab rounded-lg border border-stone-300 bg-stone-50 px-3 py-1.5 text-xs font-semibold text-stone-800 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing">{paused ? "Resume live log" : "Pause live log"}</button>
    </div>
    {error ? <p role="alert" className="mb-3 text-sm text-red-700">{error}</p> : null}
    <div className="overflow-hidden rounded-xl border border-[#44403c] bg-[#171b19] text-[#d6e4dc] shadow-inner">
      <div className="flex items-center justify-between gap-3 border-b border-[#37433c] px-4 py-3 font-mono text-xs text-[#a4b9ac]"><span><span aria-hidden="true" className="mr-2 text-emerald-300">&gt;_</span>Client event stream</span><span>{paused ? "PAUSED" : "LIVE · 10s"}</span></div>
      <div ref={viewport} onScroll={() => {
        const node = viewport.current;
        if (!node) return;
        const atBottom = node.scrollHeight - node.scrollTop - node.clientHeight < 48;
        followLatest.current = atBottom;
        setFollowing(atBottom);
      }} role="log" aria-label="Timestamped client events, newest at the bottom" aria-live="off" tabIndex={0} className="max-h-[32rem] min-h-64 overflow-x-hidden overflow-y-auto px-4 py-3 font-mono text-xs leading-5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-emerald-400">
        {!timeline ? <p role="status">{error ? "Event log unavailable." : "Loading events…"}</p> : timeline.events.length === 0 ? <p>No recorded events for this client yet.</p> : timeline.events.map(event => <DiagnosticRow key={event.id} event={event} />)}
        {timeline && <p aria-hidden="true" className="mt-2 text-[#94aa9b]"><span className="mr-2 text-emerald-300">&gt;</span>{paused ? "Live output paused" : "Waiting for events"}<span className="ml-2 inline-block h-3 w-1.5 translate-y-0.5 bg-emerald-300" /></p>}
      </div>
    </div>
    {!following && <button type="button" onClick={() => { followLatest.current = true; setFollowing(true); if (viewport.current) viewport.current.scrollTop = viewport.current.scrollHeight; }} className="mt-2 cursor-grab rounded-lg border border-stone-300 px-3 py-1.5 text-xs font-semibold text-stone-800 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-emerald-700">Jump to latest</button>}
    <p className="mt-3 text-xs leading-5 text-stone-500">{timeline ? `Checked ${timestamp(timeline.checked_at)}. ` : ""}Latest 200 events, newest at the bottom. Queued changes includes work in progress and returns to zero once processed. Published revision is the cumulative processed version. Worker stage logs cover the last 30 days; earlier attempts may show only their last status. Clinical content is excluded.</p>
  </section>;
}
