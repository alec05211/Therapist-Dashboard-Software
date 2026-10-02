"use client";

import { useMemo, useState } from "react";
import type { Appointment, SessionProcessingState, TranscriptListItem } from "@/lib/types";

export type SessionCard = {
  id: string;
  label: string;
  date: Date;
  isAvailable: boolean;
  isProcessing?: boolean;
};

type Props = {
  transcripts: TranscriptListItem[];
  appointments?: Appointment[];
  activeId: string | null;
  error: string | null;
  onOpen: (id: string) => void;
  onSelectScheduled: (session: SessionCard) => void;
  onEditSchedule?: () => void;
  processingSession?: { appointmentId: string; state: SessionProcessingState } | null;
};

function sessionCards(transcripts: TranscriptListItem[], appointments: Appointment[] = [], processingAppointmentId?: string): SessionCard[] {
  const available = transcripts.map((transcript) => ({
    id: transcript.id,
    label: transcript.label,
    date: new Date(transcript.created_at ?? Date.now()),
    isAvailable: true,
  }));
  const placeholders = appointments.filter(item => item.status === "scheduled" || item.status === "confirmed" || item.id === processingAppointmentId).map(item => ({
    id: item.id,
    label: item.client_name || "Scheduled session",
    date: new Date(item.starts_at),
    isAvailable: false,
    isProcessing: item.id === processingAppointmentId,
  }));
  return [...available, ...placeholders].sort((a, b) => a.date.getTime() - b.date.getTime());
}

export function nextScheduledSession(transcripts: TranscriptListItem[], appointments: Appointment[] = []): SessionCard | null {
  const cards = sessionCards(transcripts, appointments);
  const completed = cards.filter(card => card.isAvailable);
  const latest = completed.at(-1)?.date.getTime() ?? -Infinity;
  return cards.find(card => !card.isAvailable && card.date.getTime() > latest) ?? null;
}

const formatDate = (date: Date) => new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(date);

function CalendarIcon() {
  return (
    <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 3v4m8-4v4M4 10h14M10 20H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v5m-4 9 1-4 5-5 3 3-5 5-4 1Zm4-7 3 3" />
    </svg>
  );
}

export function SessionCardCarousel({ transcripts, appointments = [], activeId, error, onOpen, onSelectScheduled, onEditSchedule, processingSession }: Props) {
  const cards = useMemo(() => sessionCards(transcripts, appointments, processingSession?.appointmentId), [transcripts, appointments, processingSession?.appointmentId]);
  const initialIndex = Math.max(cards.findIndex((card) => card.id === activeId), 0);
  const [centerIndex, setCenterIndex] = useState(initialIndex);
  const [hasInteracted, setHasInteracted] = useState(false);
  const cardWidth = "((100cqw - 48px) / 3.4)";
  const trackOffset = `calc(50cqw - ${cardWidth} / 2 - ${centerIndex} * (${cardWidth} + 12px))`;
  const move = (direction: -1 | 1) => {
    const nextIndex = Math.max(0, Math.min(cards.length - 1, centerIndex + direction));
    setHasInteracted(true);
    setCenterIndex(nextIndex);
  };
  const selectCard = (index: number, card: SessionCard) => {
    setHasInteracted(true);
    setCenterIndex(index);
    if (card.isAvailable) onOpen(card.id);
    else onSelectScheduled(card);
  };

  return (
    <section className="session-history-carousel relative overflow-hidden rounded-2xl border border-stone-200 bg-white p-5 shadow-sm" aria-label="Session history">
      {error ? <p className="mb-3 text-sm text-red-700">{error}</p> : null}
      <div className="relative -mx-5">
        <div className="session-carousel-viewport overflow-hidden" style={{ containerType: "inline-size" }}>
          {cards.length === 0 ? <div className="mx-5 flex min-h-28 items-center justify-center rounded-xl border border-stone-200 bg-stone-50 px-4 pt-7 text-sm text-stone-600">No sessions scheduled yet.</div> : <div className="session-carousel-track flex gap-3" style={{ transform: `translateX(${trackOffset})`, transition: hasInteracted ? undefined : "none" }}>
            {cards.map((card, index) => <button key={card.id} type="button" onClick={() => selectCard(index, card)} style={{ flexBasis: `calc(${cardWidth})` }} className={`session-carousel-card relative min-h-28 min-w-0 shrink-0 cursor-grab rounded-xl border px-3 pb-3 pt-12 text-left transition-[border-color,background-color,box-shadow] duration-200 ease-out active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${index === centerIndex ? "border-emerald-700 bg-emerald-50 shadow-sm" : "border-stone-200 bg-stone-50 hover:border-stone-400 hover:bg-stone-100 hover:shadow-sm"} ${!card.isAvailable && !card.isProcessing ? "opacity-70" : ""}`} aria-current={card.id === activeId ? "true" : undefined} aria-busy={card.isProcessing || undefined}>
              {card.isProcessing ? <span aria-hidden="true" className="absolute right-3 top-3 size-3.5 animate-spin rounded-full border-2 border-stone-300 border-t-stone-700 motion-reduce:animate-none" /> : null}
              <span className="block truncate text-[10px] font-semibold uppercase tracking-wide text-emerald-800 sm:text-xs">{card.isProcessing ? "Complete" : card.isAvailable ? "Completed" : "Scheduled"}</span>
              <strong className="mt-0.5 block truncate text-xs text-stone-900 sm:text-sm">{formatDate(card.date)}</strong>
              {card.isProcessing ? <span className="mt-2 block text-xs font-medium leading-4 text-stone-600" role="status"><span className="sr-only">Upload secure. You can leave this page. </span>Hang tight while the transcript and clinical note are prepared<span aria-hidden="true" className="processing-ellipsis inline-block w-5 text-left"><span>.</span><span>.</span><span>.</span></span></span> : <span className="mt-2 block truncate text-xs font-medium text-stone-600">{card.isAvailable ? card.label : "Session details pending"}</span>}
            </button>)}
          </div>}
        </div>
        <button type="button" onClick={() => move(-1)} disabled={centerIndex === 0} className="absolute left-4 top-1/2 z-10 grid size-10 -translate-y-1/2 cursor-grab place-items-center rounded-full border border-stone-300 bg-stone-100 text-xl text-stone-700 shadow-sm hover:bg-stone-200 active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700" aria-label="Show older sessions">‹</button>
        <button type="button" onClick={() => move(1)} disabled={cards.length === 0 || centerIndex === cards.length - 1} className="absolute right-4 top-1/2 z-10 grid size-10 -translate-y-1/2 cursor-grab place-items-center rounded-full border border-stone-300 bg-stone-100 text-xl text-stone-700 shadow-sm hover:bg-stone-200 active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700" aria-label="Show more recent sessions">›</button>
      </div>
      <div className="absolute inset-x-5 top-3 z-10 flex items-start justify-between gap-4">
        <h2 className="text-base font-bold tracking-tight text-stone-900">Session History</h2>
        {onEditSchedule && <button type="button" onClick={onEditSchedule} aria-label="Edit session schedule" title="Edit session dates and recurring schedule" className="inline-flex size-9 cursor-grab items-center justify-center rounded-xl border border-stone-300 bg-stone-100 text-xs font-bold text-stone-700 shadow-sm hover:bg-stone-200 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"><CalendarIcon /></button>}
      </div>
    </section>
  );
}
