"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { TranscriptListItem } from "@/lib/types";

type SessionCard = {
  id: string;
  label: string;
  date: Date;
  isAvailable: boolean;
};

const completedSessionDates: Record<string, string> = {
  "heartwell-sadic-session-01": "2026-08-10T15:00:00-04:00",
  "heartwell-sadic-session-02": "2026-08-17T15:00:00-04:00",
  "heartwell-sadic-session-03": "2026-08-24T15:00:00-04:00",
  "heartwell-sadic-session-04": "2026-08-31T15:00:00-04:00",
  "heartwell-sadic-session-05": "2026-09-07T15:00:00-04:00",
  "heartwell-sadic-session-06": "2026-09-14T15:00:00-04:00",
};

const upcomingSessionDates = [
  "2026-09-21T15:00:00-04:00",
  "2026-09-28T15:00:00-04:00",
  "2026-10-05T15:00:00-04:00",
  "2026-10-12T15:00:00-04:00",
  "2026-10-19T15:00:00-04:00",
  "2026-10-26T15:00:00-04:00",
  "2026-11-02T15:00:00-05:00",
  "2026-11-09T15:00:00-05:00",
];

type Props = {
  transcripts: TranscriptListItem[];
  activeId: string | null;
  error: string | null;
  onOpen: (id: string) => void;
  onSelectScheduled: () => void;
  onEditSchedule: () => void;
};

function sessionCards(transcripts: TranscriptListItem[]): SessionCard[] {
  const available = transcripts.map((transcript) => ({
    id: transcript.id,
    label: transcript.label,
    date: new Date(completedSessionDates[transcript.id] ?? transcript.created_at ?? Date.now()),
    isAvailable: true,
  }));
  const placeholders = upcomingSessionDates.map((date, index) => ({
    id: `planned-${index + 1}`,
    label: "Elena Sadić · Jeremy Heartwell",
    date: new Date(date),
    isAvailable: false,
  }));
  return [...available, ...placeholders].sort((a, b) => a.date.getTime() - b.date.getTime());
}

const formatDate = (date: Date) => new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(date);

function CalendarIcon() {
  return (
    <svg aria-hidden="true" className="size-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v3m10.5-3v3M4.5 9.75h15M5.63 4.5h12.74c.62 0 1.13.5 1.13 1.13v12.74c0 .62-.5 1.13-1.13 1.13H5.63c-.62 0-1.13-.5-1.13-1.13V5.63c0-.62.5-1.13 1.13-1.13Z" />
    </svg>
  );
}

export function SessionCardCarousel({ transcripts, activeId, error, onOpen, onSelectScheduled, onEditSchedule }: Props) {
  const cards = useMemo(() => sessionCards(transcripts), [transcripts]);
  const initialIndex = Math.max(cards.findIndex((card) => card.id === activeId), 0);
  const [centerIndex, setCenterIndex] = useState(initialIndex);
  const viewport = useRef<HTMLDivElement>(null);
  const [viewportWidth, setViewportWidth] = useState(0);
  useEffect(() => {
    const node = viewport.current;
    if (!node) return;
    const measure = () => setViewportWidth(node.clientWidth);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  const cardGap = 12;
  const cardWidth = Math.max(0, (viewportWidth - cardGap * 4) / 3.4);
  const trackOffset = -((centerIndex - 2) * (cardWidth + cardGap) + cardWidth * 0.8);
  const move = (direction: -1 | 1) => {
    const nextIndex = Math.max(0, Math.min(cards.length - 1, centerIndex + direction));
    setCenterIndex(nextIndex);
  };
  const selectCard = (index: number, card: SessionCard) => {
    setCenterIndex(index);
    if (card.isAvailable) onOpen(card.id);
    else onSelectScheduled();
  };

  return (
    <section className="session-history-carousel relative overflow-hidden rounded-2xl border border-stone-200 bg-white p-5 shadow-sm" aria-label="Session history">
      {error ? <p className="mb-3 text-sm text-red-700">{error}</p> : null}
      <div className="relative -mx-5">
        <div ref={viewport} className="session-carousel-viewport overflow-hidden">
          <div className="session-carousel-track flex gap-3" style={{ transform: `translateX(${trackOffset}px)` }}>
            {cards.map((card, index) => <button key={card.id} type="button" onClick={() => selectCard(index, card)} style={{ flexBasis: `${cardWidth}px` }} className={`session-carousel-card min-h-28 shrink-0 cursor-grab rounded-xl border px-3 pb-3 pt-12 text-left transition-[border-color,background-color,box-shadow] duration-200 ease-out active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${index === centerIndex ? "border-emerald-700 bg-emerald-50 shadow-sm" : "border-stone-200 bg-stone-50 hover:border-stone-400 hover:bg-stone-100 hover:shadow-sm"} ${!card.isAvailable ? "opacity-70" : ""}`} aria-current={card.id === activeId ? "true" : undefined}>
              <span className="block truncate text-[10px] font-semibold uppercase tracking-wide text-emerald-800 sm:text-xs">{card.isAvailable ? "Completed" : "Scheduled"}</span>
              <strong className="mt-0.5 block truncate text-xs text-stone-900 sm:text-sm">{formatDate(card.date)}</strong>
              <span className="mt-2 block truncate text-xs font-medium text-stone-600">{card.isAvailable ? card.label : "Session details pending"}</span>
            </button>)}
          </div>
        </div>
        <button type="button" onClick={() => move(-1)} disabled={centerIndex === 0} className="absolute left-4 top-1/2 z-10 grid size-10 -translate-y-1/2 cursor-grab place-items-center rounded-full border border-stone-300 bg-stone-100 text-xl text-stone-700 shadow-sm hover:bg-stone-200 active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700" aria-label="Show older sessions">‹</button>
        <button type="button" onClick={() => move(1)} disabled={centerIndex === cards.length - 1} className="absolute right-4 top-1/2 z-10 grid size-10 -translate-y-1/2 cursor-grab place-items-center rounded-full border border-stone-300 bg-stone-100 text-xl text-stone-700 shadow-sm hover:bg-stone-200 active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700" aria-label="Show more recent sessions">›</button>
      </div>
      <div className="absolute inset-x-5 top-3 z-10 flex items-start justify-between gap-4">
        <h2 className="text-base font-bold tracking-tight text-stone-900">Session History</h2>
        <button type="button" onClick={onEditSchedule} className="inline-flex cursor-grab items-center gap-1.5 rounded-md border border-stone-300 bg-stone-100 px-3 py-1.5 text-xs font-bold text-stone-700 shadow-sm hover:bg-stone-200 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"><CalendarIcon />Edit schedule</button>
      </div>
    </section>
  );
}
