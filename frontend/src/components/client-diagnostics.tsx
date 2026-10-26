"use client";

import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

type Event = { id: string; timestamp: string; message: string; level: "info" | "warning" | "error"; details: Record<string, number | string> };
type Timeline = { events: Event[]; checked_at: string; retention_days: number; summary: { status: string; desired_revision: number; published_revision: number; attempt_count: number; error: string | null } };

function timestamp(value: string) {
  return new Date(value).toLocaleString(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false, timeZoneName: "short" });
}

function DiagnosticRow({ event }: { event: Event }) {
  const tooltipId = useId();
  const row = useRef<HTMLButtonElement>(null);
  const [position, setPosition] = useState<{ left: number; top: number; above: boolean } | null>(null);
  const details = Object.entries(event.details);
  const description = `${timestamp(event.timestamp)}. ${event.level.toUpperCase()}. ${event.message}${details.length ? `. ${details.map(([key, value]) => `${key}: ${value}`).join(", ")}` : ""}`;
  const show = () => {
    const bounds = row.current?.getBoundingClientRect();
    if (!bounds) return;
    const above = bounds.top > window.innerHeight / 2;
    setPosition({ left: Math.max(8, Math.min(bounds.left, window.innerWidth - Math.min(420, window.innerWidth - 16) - 8)), top: above ? bounds.top - 8 : bounds.bottom + 8, above });
  };
  useEffect(() => {
    if (!position) return;
    const dismiss = () => setPosition(null);
    window.addEventListener("scroll", dismiss, true);
    window.addEventListener("resize", dismiss);
    return () => { window.removeEventListener("scroll", dismiss, true); window.removeEventListener("resize", dismiss); };
  }, [position]);

  return <>
    <button ref={row} type="button" aria-label={description} aria-describedby={position ? tooltipId : undefined} onMouseEnter={show} onMouseLeave={() => { if (document.activeElement !== row.current) setPosition(null); }} onFocus={show} onBlur={() => setPosition(null)} onClick={show} onKeyDown={key => { if (key.key === "Escape") setPosition(null); }} className="grid w-full cursor-grab grid-cols-[9rem_minmax(0,1fr)] items-center gap-3 border-b border-[#29372f] py-2 text-left last:border-0 hover:bg-[#223029] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-emerald-400 active:cursor-grabbing sm:grid-cols-[12rem_minmax(0,1fr)]">
      <time dateTime={event.timestamp} className="truncate whitespace-nowrap text-[#94aa9b]">{timestamp(event.timestamp)}</time>
      <span className={`truncate whitespace-nowrap ${event.level === "error" ? "text-[#ffb3a7]" : event.level === "warning" ? "text-[#efd39a]" : "text-[#d6e4dc]"}`}>[{event.level.toUpperCase()}] {event.message}</span>
    </button>
    {position ? createPortal(<div id={tooltipId} role="tooltip" className="pointer-events-none fixed z-[100] w-[420px] max-w-[calc(100vw-16px)] whitespace-normal rounded-lg border border-[#53675a] bg-[#202922] p-3 font-mono text-xs leading-5 text-[#d6e4dc] shadow-xl" style={{ left: position.left, top: position.top, transform: position.above ? "translateY(-100%)" : undefined }}>
      <div className="text-[#a4b9ac]">{new Date(event.timestamp).toLocaleString(undefined, { dateStyle: "full", timeStyle: "long" })} · {event.level.toUpperCase()}</div>
      <p className="mt-1 break-words">{event.message}</p>
      {details.length ? <dl className="mt-2 border-t border-[#37433c] pt-2">{details.map(([key, value]) => <div key={key} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3"><dt className="break-words text-[#a4b9ac]">{key.replaceAll("_", " ")}</dt><dd className="break-all">{value}</dd></div>)}</dl> : null}
    </div>, document.body) : null}
  </>;
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
      <div role="log" aria-label="Timestamped client events, newest first" aria-live="off" tabIndex={0} className="max-h-[32rem] min-h-64 overflow-x-hidden overflow-y-auto px-4 py-3 font-mono text-xs leading-6 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-emerald-400">
        {!timeline ? <p role="status">{error ? "Event log unavailable." : "Loading events…"}</p> : timeline.events.length === 0 ? <p>No recorded events for this client yet.</p> : timeline.events.map(event => <DiagnosticRow key={event.id} event={event} />)}
      </div>
    </div>
    <p className="mt-3 text-xs leading-5 text-stone-500">{timeline ? `Checked ${timestamp(timeline.checked_at)}. ` : ""}Newest 200 events. Worker stage logs cover the last 30 days; earlier attempts may show only their last status. Clinical content is excluded.</p>
  </section>;
}
