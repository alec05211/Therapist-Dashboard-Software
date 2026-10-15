"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { createPortal } from "react-dom";
import { api } from "@/lib/api";
import { JOURNEY_CATEGORIES, type JourneyCategory } from "@/lib/journey-categories";
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
    entries: result.key === key ? result.entries.filter(entry => entry.status === "proposed") : [],
    error: error?.key === key ? error.message : null,
    onSaved: (updated: ClientJourneyEntry, dismissedEntryIds: string[]) => setResult(previous => ({
      ...previous,
      entries: previous.entries.map((entry) => entry.id === updated.id
        ? updated
        : dismissedEntryIds.includes(entry.id) ? { ...entry, status: "rejected" } : entry),
    })),
  };
}

const control = "cursor-grab rounded-xl border border-stone-300 px-3 py-2 text-xs font-semibold active:cursor-grabbing disabled:cursor-wait disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700";

export function QuoteReview({ entries, recordContext, onSaved }: {
  entries: ClientJourneyEntry[];
  recordContext: LongitudinalRecordContext;
  onSaved: (entry: ClientJourneyEntry, dismissedEntryIds: string[]) => void;
}) {
  const entry = entries.find((candidate) => candidate.status === "accepted") ?? entries[0];
  const [text, setText] = useState(entry.text);
  const suggestedCategories = entries.flatMap((candidate) => candidate.categories?.length
    ? candidate.categories
    : [candidate.category]);
  const [categories, setCategories] = useState<JourneyCategory[]>(suggestedCategories.length
    ? JOURNEY_CATEGORIES.map((option) => option.value).filter((value) => suggestedCategories.includes(value))
    : ["important_quote"]);
  const [saving, setSaving] = useState<"capture" | "dismiss" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const guidanceId = useId();
  const duplicateEntryIds = entries.filter((candidate) => candidate.id !== entry.id).map((candidate) => candidate.id);
  const selectedCategoryLabels = JOURNEY_CATEGORIES
    .filter((option) => categories.includes(option.value))
    .map((option) => option.label);
  const categorySummary = [
    selectedCategoryLabels.slice(0, 3).join(", "),
    selectedCategoryLabels.length > 3 ? `+${selectedCategoryLabels.length - 3} more` : "",
  ].filter(Boolean).join(" ");
  const toggleCategory = (category: JourneyCategory) => {
    setCategories((current) => {
      if (current.includes(category)) return current.length === 1 ? current : current.filter((value) => value !== category);
      return JOURNEY_CATEGORIES.map((option) => option.value).filter((value) => current.includes(value) || value === category);
    });
    setSaved(false);
  };
  const save = async (status: "accepted" | "rejected" | "stale") => {
    setSaving(status === "accepted" ? "capture" : "dismiss"); setError(null); setSaved(false);
    try {
      const result = await api.reviewClientJourneyEntry(recordContext.organizationId, recordContext.clientId, entry.id, {
        category: categories[0], categories, duplicate_entry_ids: duplicateEntryIds, text: text.trim(), status,
      });
      onSaved({ ...entry, category: result.categories[0], categories: result.categories, text: text.trim(), status: result.status }, result.dismissed_entry_ids);
      if (status === "accepted") setSaved(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save quote guidance."); }
    finally { setSaving(null); }
  };
  return <div className="relative my-3 rounded-xl border border-stone-300 bg-white p-4 text-left">
    <span className="group absolute bottom-3 left-3 z-10">
      <button type="button" aria-label="About captured insights" aria-describedby={guidanceId} className="grid size-7 cursor-help place-items-center rounded-full border border-stone-300 bg-stone-50 text-stone-600 transition-colors duration-200 ease-out hover:border-stone-400 hover:text-stone-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">
        <svg viewBox="0 0 20 20" className="size-4" fill="none" aria-hidden="true"><circle cx="10" cy="10" r="7.25" stroke="currentColor" strokeWidth="1.5" /><path d="M10 8.7v4.4M10 6.2v.1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
      </button>
      <span id={guidanceId} role="tooltip" className="pointer-events-none invisible absolute bottom-9 left-0 w-72 rounded-xl border border-stone-300 bg-white px-3 py-2 text-xs font-normal leading-5 text-stone-700 opacity-0 shadow-md transition-opacity duration-200 ease-out group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100">
        Your interpretation stays linked to the original transcript evidence. Capturing it guides future Insights synthesis and any downstream pre-session brief.
      </span>
    </span>
    <div className="grid gap-1 text-xs font-medium text-stone-700">Use as
      <details className="group relative">
        <summary className="flex cursor-grab list-none items-center justify-between gap-3 rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 text-sm font-normal text-stone-900 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 [&::-webkit-details-marker]:hidden">
          <span className="min-w-0 truncate">{categorySummary}</span>
          <svg viewBox="0 0 20 20" className="size-4 shrink-0 text-stone-500 transition-transform group-open:rotate-180" fill="none" aria-hidden="true"><path d="m5.5 7.5 4.5 4.5 4.5-4.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </summary>
        <div className="relative z-20 mt-1 grid w-full grid-cols-2 gap-1 rounded-xl border border-stone-300 bg-white p-1.5 shadow-sm max-sm:grid-cols-1">
          {JOURNEY_CATEGORIES.map((option) => <label key={option.value} className="flex min-w-0 cursor-grab items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-normal text-stone-800 transition-colors hover:bg-stone-100 active:cursor-grabbing">
            <input type="checkbox" aria-label={option.label} checked={categories.includes(option.value)} onChange={() => toggleCategory(option.value)} disabled={Boolean(saving)} className="size-4 cursor-grab accent-emerald-800 active:cursor-grabbing disabled:cursor-wait" />
            <span>{option.label}</span>
          </label>)}
        </div>
      </details>
    </div>
    <label className="mt-3 grid gap-1 text-xs font-medium text-stone-700">What should future synthesis focus on?
      <textarea value={text} onChange={event => { setText(event.target.value); setSaved(false); }} maxLength={4000} rows={3} disabled={Boolean(saving)} className="resize-y rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 text-sm leading-6 text-stone-900 focus:outline-none focus-visible:border-stone-500" />
    </label>
    {saved && <p role="status" className="mt-3 text-xs text-emerald-800">Insight captured for future synthesis.</p>}
    {error && <p role="alert" className="mt-3 text-xs text-red-700">{error}</p>}
    <div className="mt-4 flex w-full flex-wrap justify-end gap-2 pl-10">
      <button type="button" disabled={Boolean(saving) || !text.trim()} onClick={() => void save(entry.status === "proposed" ? "rejected" : "stale")} className={`${control} text-stone-700`}>{saving === "dismiss" ? "Dismissing…" : "Dismiss"}</button>
      <button type="button" disabled={Boolean(saving) || !text.trim()} onClick={() => void save("accepted")} className={`${control} bg-emerald-800 text-white`}>{saving === "capture" ? "Capturing…" : "Capture Insight"}</button>
    </div>
  </div>;
}

type InspectorPosition = { left: number; top: number };

const viewportMargin = 16;
const inspectorWidth = 640;

const initialInspectorPosition = (stackIndex = 0): InspectorPosition => {
  if (typeof window === "undefined") return { left: viewportMargin, top: viewportMargin };
  const width = Math.min(inspectorWidth, window.innerWidth - viewportMargin * 2);
  return {
    left: Math.max(viewportMargin, window.innerWidth - width - 24 - stackIndex * 28),
    top: Math.max(viewportMargin, window.innerHeight - 560 + stackIndex * 28),
  };
};

export function FloatingQuoteInspector({ id, entries, recordContext, onSaved, onClose, stackIndex = 0, active = false, onActivate }: {
  id: string;
  entries: ClientJourneyEntry[];
  recordContext: LongitudinalRecordContext;
  onSaved: (entry: ClientJourneyEntry, dismissedEntryIds: string[]) => void;
  onClose: () => void;
  stackIndex?: number;
  active?: boolean;
  onActivate?: () => void;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const drag = useRef<{ pointerId: number; offsetX: number; offsetY: number } | null>(null);
  const [position, setPosition] = useState<InspectorPosition>(() => initialInspectorPosition(stackIndex));

  const clampPosition = (left: number, top: number): InspectorPosition => {
    const bounds = panel.current?.getBoundingClientRect();
    const width = bounds?.width ?? Math.min(inspectorWidth, window.innerWidth - viewportMargin * 2);
    const height = bounds?.height ?? 400;
    return {
      left: Math.min(Math.max(viewportMargin, left), Math.max(viewportMargin, window.innerWidth - width - viewportMargin)),
      top: Math.min(Math.max(viewportMargin, top), Math.max(viewportMargin, window.innerHeight - height - viewportMargin)),
    };
  };

  useEffect(() => {
    const keepInView = () => setPosition(previous => {
      const next = clampPosition(previous.left, previous.top);
      return next.left === previous.left && next.top === previous.top ? previous : next;
    });
    const closeOnEscape = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    const frame = window.requestAnimationFrame(keepInView);
    window.addEventListener("resize", keepInView);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", keepInView);
      document.removeEventListener("keydown", closeOnEscape);
    };
  });

  const startDrag = (event: PointerEvent<HTMLButtonElement>) => {
    if (window.matchMedia("(max-width: 767px)").matches) return;
    const bounds = panel.current?.getBoundingClientRect();
    if (!bounds) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { pointerId: event.pointerId, offsetX: event.clientX - bounds.left, offsetY: event.clientY - bounds.top };
  };
  const moveDrag = (event: PointerEvent<HTMLButtonElement>) => {
    if (drag.current?.pointerId !== event.pointerId) return;
    setPosition(clampPosition(event.clientX - drag.current.offsetX, event.clientY - drag.current.offsetY));
  };
  const stopDrag = (event: PointerEvent<HTMLButtonElement>) => {
    if (drag.current?.pointerId !== event.pointerId) return;
    drag.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  };
  const moveWithKeyboard = (event: KeyboardEvent<HTMLButtonElement>) => {
    const directions: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    const direction = directions[event.key];
    if (!direction) return;
    event.preventDefault();
    const step = event.shiftKey ? 48 : 16;
    setPosition(previous => clampPosition(previous.left + direction[0] * step, previous.top + direction[1] * step));
  };

  if (typeof document === "undefined") return null;
  return createPortal(
    <div ref={panel} id={id} role="dialog" aria-label="Evidence review" data-no-segment-playback onPointerDown={onActivate} style={{ left: position.left, top: position.top }} className={`fixed ${active ? "z-[80] border-emerald-700" : "z-[70] border-stone-300"} flex w-[min(40rem,calc(100vw-2rem))] flex-col overflow-visible rounded-2xl border bg-white text-left shadow-xl transition-[border-color] duration-200 ease-out max-md:!inset-x-0 max-md:!bottom-0 max-md:!top-auto max-md:!w-full max-md:!max-w-none max-md:max-h-[calc(100vh-2rem)] max-md:overflow-hidden max-md:rounded-b-none`}>
      <div className="relative flex h-10 shrink-0 items-center justify-center border-b border-stone-200 bg-stone-50">
        <button type="button" aria-label="Move evidence inspector" title="Drag to move · Arrow keys also reposition" onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={stopDrag} onPointerCancel={stopDrag} onKeyDown={moveWithKeyboard} className="flex h-full flex-1 touch-none cursor-grab items-center justify-center text-stone-500 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-emerald-700 max-md:cursor-default">
          <svg viewBox="0 0 28 12" className="h-3 w-7" fill="currentColor" aria-hidden="true"><circle cx="8" cy="3" r="1.25" /><circle cx="14" cy="3" r="1.25" /><circle cx="20" cy="3" r="1.25" /><circle cx="8" cy="9" r="1.25" /><circle cx="14" cy="9" r="1.25" /><circle cx="20" cy="9" r="1.25" /></svg>
        </button>
        <button type="button" aria-label="Close evidence inspector" onClick={onClose} className="absolute right-2 grid size-8 cursor-grab place-items-center rounded-full text-stone-600 hover:bg-stone-200 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-emerald-700">
          <svg viewBox="0 0 20 20" className="size-4" fill="none" aria-hidden="true"><path d="m5 5 10 10M15 5 5 15" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" /></svg>
        </button>
      </div>
      <div className="min-h-0 overflow-visible px-4 pb-2 max-md:overflow-y-auto">
        <QuoteReview key={entries.find((entry) => entry.status === "accepted")?.id ?? entries[0]?.id} entries={entries} recordContext={recordContext} onSaved={onSaved} />
      </div>
    </div>,
    document.body,
  );
}
