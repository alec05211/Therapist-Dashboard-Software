"use client";

import { useMemo, useState } from "react";
import { mergeReservedTimes, subtractReservedTimes } from "@/lib/reserved-time";
import type { Appointment } from "@/lib/types";

type BusyTime = { starts_at: string; ends_at: string };
type Props = {
  appointments: Appointment[];
  busyTimes: BusyTime[];
  busy: boolean;
  durationMinutes: number;
  onReschedule: (appointment: Appointment, startsAt: Date) => Promise<void>;
  onCreate: (startsAt: Date, appointmentType: "one_time" | "make_up") => Promise<void>;
  onCancel: (appointment: Appointment) => Promise<void>;
};

const DAY_START = 9 * 60;
const DAY_END = 17 * 60;
const SLOT_MINUTES = 30;
const SLOT_HEIGHT = 34;
const SNAP_MINUTES = 10;
const snapSlots = Array.from({ length: (DAY_END - DAY_START) / SNAP_MINUTES }, (_, index) => DAY_START + index * SNAP_MINUTES);
const DAYS = 5;
const slots = Array.from({ length: (DAY_END - DAY_START) / SLOT_MINUTES }, (_, index) => DAY_START + index * SLOT_MINUTES);

function startOfWeek(value: Date) {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  return date;
}

function addDays(value: Date, count: number) {
  const date = new Date(value);
  date.setDate(date.getDate() + count);
  return date;
}

function atTime(day: Date, minute: number) {
  const date = new Date(day);
  date.setHours(Math.floor(minute / 60), minute % 60, 0, 0);
  return date;
}

function minutesIntoDay(value: Date) {
  return value.getHours() * 60 + value.getMinutes();
}

function overlaps(start: Date, end: Date, otherStart: string, otherEnd: string) {
  return new Date(otherStart) < end && new Date(otherEnd) > start;
}

const timeLabel = (minute: number) => new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(atTime(new Date(), minute));
const dayLabel = (day: Date) => new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric" }).format(day);
const weekLabel = (start: Date) => {
  const end = addDays(start, 4);
  const first = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(start);
  const last = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(end);
  return `${first} – ${last}`;
};

export function ClientScheduleWeek({ appointments, busyTimes, busy, durationMinutes, onReschedule, onCreate, onCancel }: Props) {
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [hoveredSlot, setHoveredSlot] = useState<string | null>(null);
  const [pendingMove, setPendingMove] = useState<{ appointment: Appointment; startsAt: Date } | null>(null);
  const [pendingCreate, setPendingCreate] = useState<Date | null>(null);
  const [newAppointmentType, setNewAppointmentType] = useState<"one_time" | "make_up">("one_time");
  const days = useMemo(() => Array.from({ length: DAYS }, (_, index) => addDays(weekStart, index)), [weekStart]);
  const weekEnd = addDays(weekStart, DAYS);
  const activeAppointments = appointments.filter(item => item.status === "scheduled" || item.status === "confirmed");
  const weekAppointments = activeAppointments.filter(item => new Date(item.starts_at) < weekEnd && new Date(item.ends_at) > weekStart);
  const reservedTimes = (excludeAppointmentId?: string) => mergeReservedTimes([
    ...busyTimes,
    ...activeAppointments.filter(item => item.id !== excludeAppointmentId),
  ], durationMinutes);
  const weekBusyTimes = subtractReservedTimes(reservedTimes(draggingId ?? undefined), activeAppointments).filter(item => new Date(item.starts_at) < weekEnd && new Date(item.ends_at) > weekStart);
  const dragging = activeAppointments.find(item => item.id === draggingId) || null;
  const draggingDuration = dragging ? Math.round((Date.parse(dragging.ends_at) - Date.parse(dragging.starts_at)) / 60_000) : 0;
  const previewStart = dragging && hoveredSlot ? new Date(hoveredSlot) : null;

  const canPlace = (start: Date, duration: number, excludeAppointmentId?: string) => {
    const end = new Date(start.getTime() + duration * 60_000);
    if (minutesIntoDay(end) > DAY_END || end.getDate() !== start.getDate()) return false;
    return !reservedTimes(excludeAppointmentId).some(item => overlaps(start, end, item.starts_at, item.ends_at));
  };

  const validDrop = (appointment: Appointment, start: Date) => {
    const duration = Math.round((new Date(appointment.ends_at).getTime() - new Date(appointment.starts_at).getTime()) / 60_000);
    return canPlace(start, duration, appointment.id);
  };

  const position = (startsAt: string, endsAt: string) => {
    const start = new Date(startsAt);
    const end = new Date(endsAt);
    const topMinutes = Math.max(DAY_START, minutesIntoDay(start)) - DAY_START;
    const visibleEnd = Math.min(DAY_END, minutesIntoDay(end));
    return {
      top: `${topMinutes / SLOT_MINUTES * SLOT_HEIGHT}px`,
      height: `${Math.max(0, (visibleEnd - Math.max(DAY_START, minutesIntoDay(start))) / SLOT_MINUTES * SLOT_HEIGHT)}px`,
    };
  };

  return <>
    <section className="rounded-xl border border-stone-300 bg-white">
      <div className="flex items-start justify-between gap-3 border-b border-stone-300 px-4 py-3">
        <div className="min-w-0">
          <h4 className="font-semibold text-stone-900">Weekly schedule</h4>
          <p className="mt-0.5 text-xs text-stone-500">Drag this client’s sessions to an available time. Gray areas are unavailable, including gaps too short for a session.</p>
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-1 self-start rounded-xl border border-stone-300 bg-stone-50 p-1">
          <button type="button" onClick={() => setWeekStart(current => addDays(current, -7))} className="cursor-grab rounded-lg px-2.5 py-1.5 text-xs font-semibold text-stone-700 hover:bg-stone-100 active:cursor-grabbing">Previous</button>
          <button type="button" onClick={() => setWeekStart(startOfWeek(new Date()))} className="cursor-grab rounded-lg px-2.5 py-1.5 text-xs font-semibold text-stone-700 hover:bg-stone-100 active:cursor-grabbing">Today</button>
          <button type="button" onClick={() => setWeekStart(current => addDays(current, 7))} className="cursor-grab rounded-lg px-2.5 py-1.5 text-xs font-semibold text-stone-700 hover:bg-stone-100 active:cursor-grabbing">Next</button>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 px-4 py-2.5">
        <p className="text-sm font-semibold text-stone-800">{weekLabel(weekStart)}</p>
        <div className="flex flex-wrap gap-3 text-[11px] font-medium text-stone-600" aria-label="Schedule legend">
          <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm border border-emerald-300 bg-emerald-50" />Client session</span>
          <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm border border-stone-400 bg-[var(--surface-inset)]" />Unavailable</span>
          <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm border border-stone-300 bg-stone-50" />Available</span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <div className="min-w-[760px]">
          <div className="grid grid-cols-[64px_repeat(5,minmax(0,1fr))] border-b border-stone-300 bg-stone-50">
            <div />
            {days.map(day => <div key={day.toISOString()} className="px-2 py-2 text-center text-xs font-semibold text-stone-700">{dayLabel(day)}</div>)}
          </div>
          <div className="grid grid-cols-[64px_repeat(5,minmax(0,1fr))]">
            <div className="relative bg-stone-50" style={{ height: slots.length * SLOT_HEIGHT }}>
              {slots.map((minute, index) => <span key={minute} className="absolute right-2 -translate-y-1/2 text-[10px] text-stone-500" style={{ top: index * SLOT_HEIGHT }}>{timeLabel(minute)}</span>)}
            </div>
            {days.map(day => {
              const dayStart = atTime(day, DAY_START);
              const dayEnd = atTime(day, DAY_END);
              const dayBusy = weekBusyTimes.filter(item => new Date(item.starts_at) < dayEnd && new Date(item.ends_at) > dayStart);
              const dayAppointments = weekAppointments.filter(item => new Date(item.starts_at) < dayEnd && new Date(item.ends_at) > dayStart);
              const dropStart = (element: HTMLDivElement, clientY: number) => {
                const offset = Math.max(0, clientY - element.getBoundingClientRect().top);
                const minute = DAY_START + Math.floor(offset / SLOT_HEIGHT * SLOT_MINUTES / SNAP_MINUTES) * SNAP_MINUTES;
                return atTime(day, Math.min(DAY_END - SNAP_MINUTES, minute));
              };
              return <div key={day.toISOString()}
                onDragOver={event => {
                  if (!dragging || busy) return;
                  const start = dropStart(event.currentTarget, event.clientY);
                  if (validDrop(dragging, start)) {
                    event.preventDefault();
                    event.dataTransfer.dropEffect = "move";
                    setHoveredSlot(start.toISOString());
                  } else {
                    event.dataTransfer.dropEffect = "none";
                    setHoveredSlot(null);
                  }
                }}
                onDragLeave={event => {
                  if (!(event.relatedTarget instanceof Node) || !event.currentTarget.contains(event.relatedTarget)) setHoveredSlot(null);
                }}
                onDrop={event => {
                  event.preventDefault();
                  if (!dragging || busy) return;
                  const start = dropStart(event.currentTarget, event.clientY);
                  setHoveredSlot(null);
                  setDraggingId(null);
                  if (validDrop(dragging, start)) setPendingMove({ appointment: dragging, startsAt: start });
                }}
                className="relative bg-stone-50"
                style={{ height: slots.length * SLOT_HEIGHT, backgroundImage: "repeating-linear-gradient(to bottom, transparent 0, transparent 67px, color-mix(in srgb, var(--border) 10%, transparent) 67px, color-mix(in srgb, var(--border) 10%, transparent) 68px)" }}>

                {snapSlots.map(minute => {
                  const start = atTime(day, minute);
                  const key = start.toISOString();
                  const availableForNewSession = canPlace(start, durationMinutes);
                  return <div key={key} onClick={() => { if (!dragging && availableForNewSession && !busy) setPendingCreate(start); }} className={`absolute inset-x-0 z-10 ${!dragging && availableForNewSession ? "cursor-grab hover:bg-stone-100 active:cursor-grabbing" : ""}`} style={{ top: (minute - DAY_START) / SLOT_MINUTES * SLOT_HEIGHT, height: SNAP_MINUTES / SLOT_MINUTES * SLOT_HEIGHT }} />;
                })}
                {dayBusy.map(item => <div
                  key={`${item.starts_at}-${item.ends_at}`}
                  aria-label={`Unavailable time: reserved appointments and gaps shorter than ${durationMinutes} minutes`}
                  onClick={event => event.stopPropagation()}
                  className="absolute inset-x-0 z-20 cursor-not-allowed bg-[var(--surface-inset)]"
                  style={{
                    top: (Math.max(dayStart.getTime(), Date.parse(item.starts_at)) - dayStart.getTime()) / 60_000 / SLOT_MINUTES * SLOT_HEIGHT,
                    height: (Math.min(dayEnd.getTime(), Date.parse(item.ends_at)) - Math.max(dayStart.getTime(), Date.parse(item.starts_at))) / 60_000 / SLOT_MINUTES * SLOT_HEIGHT,
                  }}
                />)}
                {previewStart && previewStart >= dayStart && previewStart < dayEnd ? <div
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-x-1 z-40 rounded-lg border-2 border-emerald-700 bg-[color-mix(in_srgb,var(--accent-surface)_80%,transparent)] px-2 py-1 text-[10px] font-semibold text-emerald-800"
                  style={position(previewStart.toISOString(), new Date(previewStart.getTime() + draggingDuration * 60_000).toISOString())}
                >{timeLabel(minutesIntoDay(previewStart))} – {timeLabel(minutesIntoDay(previewStart) + draggingDuration)}</div> : null}
                {dayAppointments.map(item => <article key={item.id} draggable={!busy} onDragStart={event => { event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", item.id); setDraggingId(item.id); }} onDragEnd={() => { setDraggingId(null); setHoveredSlot(null); }} className={`absolute inset-x-1 z-30 select-none overflow-hidden rounded-lg border border-emerald-300 bg-emerald-50 px-2 py-1.5 text-emerald-800 shadow-sm ${busy ? "cursor-wait" : "cursor-grab active:cursor-grabbing"} ${draggingId === item.id ? "opacity-50" : ""}`} style={position(item.starts_at, item.ends_at)}>
                  <div className="flex items-start justify-between gap-1">
                    <div className="min-w-0"><p className="truncate text-[11px] font-bold">{new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(new Date(item.starts_at))}</p><p className="truncate text-[10px] font-medium">{item.appointment_type.replace("_", "-")}</p></div>
                    <button type="button" disabled={busy} onPointerDown={event => event.stopPropagation()} onClick={event => { event.stopPropagation(); void onCancel(item); }} aria-label={`Cancel session on ${dayLabel(new Date(item.starts_at))}`} className="cursor-grab rounded px-1 text-[10px] font-bold text-emerald-800 hover:bg-emerald-50 active:cursor-grabbing disabled:cursor-wait">Cancel</button>
                  </div>
                </article>)}
              </div>;
            })}
          </div>
        </div>
      </div>
    </section>
    {pendingMove ? <div role="presentation" onMouseDown={event => { if (event.target === event.currentTarget && !busy) setPendingMove(null); }} onKeyDown={event => { if (event.key === "Escape" && !busy) setPendingMove(null); }} className="fixed inset-0 z-50 grid place-items-center bg-stone-950/35 p-4 backdrop-blur-[3px]">
      <section role="dialog" aria-modal="true" aria-labelledby="reschedule-title" aria-describedby="reschedule-description" className="w-full max-w-md rounded-2xl border border-stone-300 bg-white p-5 text-left shadow-xl">
        <h3 id="reschedule-title" className="text-lg font-semibold text-stone-900">Reschedule this session?</h3>
        <p id="reschedule-description" className="mt-3 text-sm leading-6 text-stone-600">The session will move to:</p>
        <p className="mt-1 rounded-xl border border-emerald-300 bg-emerald-50 px-3 py-2.5 text-sm font-semibold text-emerald-800">{new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }).format(pendingMove.startsAt)}</p>
        <p className="mt-3 text-xs leading-5 text-stone-500">{pendingMove.appointment.appointment_type === "recurring" ? "This change applies only to this session. Sessions will resume at the normal time next week." : "This change applies only to this session."}</p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" disabled={busy} onClick={() => setPendingMove(null)} className="cursor-grab rounded-xl border border-stone-300 bg-stone-50 px-4 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-100 active:cursor-grabbing disabled:cursor-wait disabled:opacity-60">Keep current time</button>
          <button type="button" autoFocus disabled={busy} onClick={() => { const move = pendingMove; void onReschedule(move.appointment, move.startsAt).finally(() => setPendingMove(null)); }} className="cursor-grab rounded-xl bg-emerald-800 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-900 active:cursor-grabbing disabled:cursor-wait disabled:opacity-60">{busy ? "Rescheduling…" : "Confirm reschedule"}</button>
        </div>
      </section>
    </div> : null}
    {pendingCreate ? <div role="presentation" onMouseDown={event => { if (event.target === event.currentTarget && !busy) setPendingCreate(null); }} onKeyDown={event => { if (event.key === "Escape" && !busy) setPendingCreate(null); }} className="fixed inset-0 z-50 grid place-items-center bg-stone-950/35 p-4 backdrop-blur-[3px]">
      <section role="dialog" aria-modal="true" aria-labelledby="create-session-title" className="w-full max-w-md rounded-2xl border border-stone-300 bg-white p-5 text-left shadow-xl">
        <h3 id="create-session-title" className="text-lg font-semibold text-stone-900">Add a session?</h3>
        <p className="mt-3 rounded-xl border border-emerald-300 bg-emerald-50 px-3 py-2.5 text-sm font-semibold text-emerald-800">{new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }).format(pendingCreate)} – {new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(new Date(pendingCreate.getTime() + durationMinutes * 60_000))}</p>
        <label className="mt-4 block text-xs font-semibold text-stone-700">Session type<select value={newAppointmentType} onChange={event => setNewAppointmentType(event.target.value as "one_time" | "make_up")} className="mt-1.5 w-full rounded-xl border border-stone-300 bg-white px-3 py-2.5 text-sm text-stone-900 focus:outline-none focus-visible:border-stone-500"><option value="one_time">One-time</option><option value="make_up">Make-up</option></select></label>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" disabled={busy} onClick={() => setPendingCreate(null)} className="cursor-grab rounded-xl border border-stone-300 bg-stone-50 px-4 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-100 active:cursor-grabbing disabled:cursor-wait disabled:opacity-60">Cancel</button>
          <button type="button" autoFocus disabled={busy} onClick={() => { const startsAt = pendingCreate; void onCreate(startsAt, newAppointmentType).finally(() => setPendingCreate(null)); }} className="cursor-grab rounded-xl bg-emerald-800 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-900 active:cursor-grabbing disabled:cursor-wait disabled:opacity-60">{busy ? "Adding…" : "Add session"}</button>
        </div>
      </section>
    </div> : null}
  </>;
}
