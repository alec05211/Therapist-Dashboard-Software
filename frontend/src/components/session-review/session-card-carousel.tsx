"use client";

import { useMemo, useState } from "react";
import type { TranscriptListItem } from "@/lib/types";

type SessionCard = {
  id: string;
  label: string;
  date: Date;
  isAvailable: boolean;
};

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
    date: transcript.created_at ? new Date(transcript.created_at) : new Date(),
    isAvailable: true,
  }));
  const newestDate = available[0]?.date ?? new Date();
  const placeholders = Array.from({ length: Math.max(9 - available.length, 0) }, (_, index) => {
    const date = new Date(newestDate);
    date.setDate(date.getDate() - (index + 1) * 7);
    return { id: `planned-${index}`, label: "Planned session", date, isAvailable: false };
  });
  return [...available, ...placeholders].sort((a, b) => b.date.getTime() - a.date.getTime());
}

const formatDate = (date: Date) => new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(date);

export function SessionCardCarousel({ transcripts, activeId, error, onOpen, onSelectScheduled, onEditSchedule }: Props) {
  const cards = useMemo(() => sessionCards(transcripts), [transcripts]);
  const initialIndex = Math.max(cards.findIndex((card) => card.id === activeId), 0);
  const [centerIndex, setCenterIndex] = useState(initialIndex);
  const [motion, setMotion] = useState<"previous" | "next">("next");
  const [motionKey, setMotionKey] = useState(0);

  const visible = Array.from({ length: 5 }, (_, position) => {
    const index = centerIndex + position - 2;
    return { card: cards[index], index, position };
  });
  const move = (direction: -1 | 1) => {
    const nextIndex = Math.max(0, Math.min(cards.length - 1, centerIndex + direction));
    if (nextIndex !== centerIndex) {
      setMotion(direction === 1 ? "next" : "previous");
      setMotionKey((current) => current + 1);
      setCenterIndex(nextIndex);
    }
  };
  const selectCard = (index: number, card: SessionCard) => {
    if (index !== centerIndex) {
      setMotion(index > centerIndex ? "next" : "previous");
      setMotionKey((current) => current + 1);
      setCenterIndex(index);
    }
    if (card.isAvailable) onOpen(card.id);
    else onSelectScheduled();
  };

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm" aria-label="Session history">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-stone-900">Session history</h2>
        <button type="button" onClick={onEditSchedule} className="cursor-grab rounded-lg border border-stone-300 px-3 py-1.5 text-xs font-semibold text-stone-700 hover:bg-stone-50 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Edit schedule</button>
      </div>
      {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      <div className="mt-4 grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 sm:gap-3">
        <button type="button" onClick={() => move(-1)} disabled={centerIndex === 0} className="grid size-10 cursor-grab place-items-center rounded-full border border-stone-300 text-xl text-stone-700 hover:bg-stone-50 active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700" aria-label="Show more recent sessions">‹</button>
        <div key={`${centerIndex}-${motionKey}`} data-motion={motion} className="session-carousel-track grid min-w-0 grid-cols-5 gap-2 sm:gap-3">
          {visible.map(({ card, index, position }) => card ? <button key={card.id} type="button" onClick={() => selectCard(index, card)} className={`min-w-0 cursor-grab rounded-xl border p-2 text-left transition-[border-color,background-color,box-shadow,transform] duration-200 ease-out hover:-translate-y-0.5 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 sm:p-3 ${position === 2 ? "border-emerald-700 bg-emerald-50 shadow-sm" : "border-stone-200 bg-stone-50 hover:border-stone-400"} ${!card.isAvailable ? "opacity-70" : ""}`} aria-current={card.id === activeId ? "true" : undefined}>
            <span className="block truncate text-[10px] font-semibold uppercase tracking-wide text-emerald-800 sm:text-xs">{card.isAvailable ? "Completed" : "Scheduled"}</span>
            <strong className="mt-1 block truncate text-xs text-stone-900 sm:text-sm">{formatDate(card.date)}</strong>
            <span className="mt-1 hidden text-xs text-stone-500 sm:block">3:00 PM</span>
            <span className="mt-2 hidden truncate text-xs font-medium text-stone-600 md:block">{card.isAvailable ? card.label : "Session details pending"}</span>
          </button> : <div key={`empty-${position}`} aria-hidden="true" />)}
        </div>
        <button type="button" onClick={() => move(1)} disabled={centerIndex === cards.length - 1} className="grid size-10 cursor-grab place-items-center rounded-full border border-stone-300 text-xl text-stone-700 hover:bg-stone-50 active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700" aria-label="Show older sessions">›</button>
      </div>
    </section>
  );
}
