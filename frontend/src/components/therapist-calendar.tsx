"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { LoadingSpinner } from "@/components/loading-spinner";
import type { Appointment } from "@/lib/types";

type CalendarView = "day" | "week" | "month";
type DateRange = { start: Date; end: Date };

const addDays = (value: Date, days: number) => {
  const date = new Date(value);
  date.setDate(date.getDate() + days);
  return date;
};

const addMonths = (value: Date, months: number) => {
  const date = new Date(value);
  date.setDate(1);
  date.setMonth(date.getMonth() + months);
  return date;
};

const startOfDay = (value: Date) => {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
  return date;
};

const startOfWeek = (value: Date) => {
  const date = startOfDay(value);
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  return date;
};

const startOfMonth = (value: Date) => {
  const date = startOfDay(value);
  date.setDate(1);
  return date;
};

const dayKey = (value: Date | string) =>
  new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value));

const monthKey = (value: Date) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}`;
const timeFormatter = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" });
const weekdayFormatter = new Intl.DateTimeFormat("en-US", { weekday: "short" });
const monthFormatter = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" });
const longDateFormatter = new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
const appointmentLabel = (appointment: Appointment) =>
  appointment.status === "cancelled" ? "Cancelled" : appointment.appointment_type.replaceAll("_", "-");

function datesInRange({ start, end }: DateRange) {
  const dates: Date[] = [];
  for (let date = new Date(start); date < end; date = addDays(date, 1)) dates.push(date);
  return dates;
}

function rangeForMonth(value: Date): DateRange {
  const monthStart = startOfMonth(value);
  const start = startOfWeek(monthStart);
  const lastDay = addDays(addMonths(monthStart, 1), -1);
  return { start, end: addDays(startOfWeek(lastDay), 7) };
}

function weeksForMonth(value: Date) {
  const days = datesInRange(rangeForMonth(value));
  return Array.from({ length: days.length / 7 }, (_, index) => days.slice(index * 7, index * 7 + 7));
}

function AppointmentCard({ appointment, compact = false }: { appointment: Appointment; compact?: boolean }) {
  return (
    <Link
      href={`/clients/${encodeURIComponent(appointment.client_id)}`}
      className={`block cursor-grab rounded-lg border text-left transition-colors duration-200 ease-out motion-reduce:transition-none active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${compact ? "p-1.5" : "p-2.5"} ${
        appointment.status === "cancelled"
          ? "border-stone-200 bg-stone-50 opacity-60 hover:border-stone-400"
          : "border-emerald-300 bg-emerald-50 hover:border-emerald-700"
      }`}
    >
      <span className={`block font-bold text-stone-900 ${compact ? "text-[11px]" : "text-xs"}`}>
        {timeFormatter.format(new Date(appointment.starts_at))}
      </span>
      <span className={`mt-0.5 block truncate text-stone-700 ${compact ? "text-[11px]" : "text-xs"}`}>
        {appointment.client_name || "Client"}
      </span>
      {!compact && (
        <span className="mt-1 block text-[10px] font-semibold uppercase tracking-wide text-stone-500">
          {appointmentLabel(appointment)}
        </span>
      )}
    </Link>
  );
}

function EmptyDay() {
  return <p className="text-xs text-stone-500">No appointments</p>;
}

function ViewControls({ view, onViewChange }: { view: CalendarView; onViewChange: (view: CalendarView) => void }) {
  return (
    <div className="inline-flex min-w-fit gap-1 rounded-xl border border-stone-300 bg-stone-50 p-1" role="group" aria-label="Calendar view">
      {(["day", "week", "month"] as const).map(option => (
        <button
          key={option}
          type="button"
          aria-pressed={view === option}
          onClick={() => onViewChange(option)}
          className={`cursor-grab rounded-lg px-3 py-1.5 text-sm font-semibold capitalize transition-colors duration-200 ease-out motion-reduce:transition-none active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${
            view === option ? "bg-emerald-50 text-emerald-900" : "text-stone-600 hover:bg-stone-100"
          }`}
        >
          {option}
        </button>
      ))}
    </div>
  );
}

export function TherapistCalendar() {
  const today = useMemo(() => startOfDay(new Date()), []);
  const [view, setView] = useState<CalendarView>("week");
  const [anchorDate, setAnchorDate] = useState(today);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [lastAgendaDate, setLastAgendaDate] = useState<Date | null>(null);
  const [visibleMonth, setVisibleMonth] = useState(startOfMonth(today));
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loadedMonths, setLoadedMonths] = useState<Set<string>>(() => new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const monthScrollRef = useRef<HTMLDivElement>(null);
  const agendaRef = useRef<HTMLElement>(null);
  const loadingMonthsRef = useRef<Set<string>>(new Set());
  const loadedMonthsRef = useRef<Set<string>>(new Set());
  const centeredMonthRef = useRef(false);
  const scrollFrameRef = useRef<number | null>(null);

  const monthStack = useMemo(
    () => Array.from({ length: 13 }, (_, index) => addMonths(startOfMonth(today), index - 6)),
    [today],
  );
  const monthWeeks = useMemo(
    () => new Map(monthStack.map(month => [monthKey(month), weeksForMonth(month)])),
    [monthStack],
  );

  const visibleRange = useMemo(() => {
    if (view === "day") {
      const start = startOfDay(anchorDate);
      return { start, end: addDays(start, 1) };
    }
    const start = startOfWeek(anchorDate);
    return { start, end: addDays(start, 7) };
  }, [anchorDate, view]);

  const days = useMemo(() => datesInRange(visibleRange), [visibleRange]);

  const mergeAppointments = useCallback((incoming: Appointment[]) => {
    setAppointments(current => {
      const byId = new Map(current.map(item => [item.id, item]));
      for (const item of incoming) byId.set(item.id, item);
      return Array.from(byId.values()).sort((a, b) => a.starts_at.localeCompare(b.starts_at));
    });
  }, []);

  const fetchRange = useCallback(async (range: DateRange, signal?: AbortSignal) => {
    const response = await fetch(
      `/api/calendar/appointments?start=${encodeURIComponent(range.start.toISOString())}&end=${encodeURIComponent(range.end.toISOString())}`,
      { cache: "no-store", signal },
    );
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "Could not load the calendar.");
    return (body.appointments || []) as Appointment[];
  }, []);

  const loadMonth = useCallback(async (month: Date) => {
    const key = monthKey(month);
    if (loadedMonthsRef.current.has(key) || loadingMonthsRef.current.has(key)) return;
    loadingMonthsRef.current.add(key);
    try {
      mergeAppointments(await fetchRange(rangeForMonth(month)));
      loadedMonthsRef.current.add(key);
      setLoadedMonths(current => new Set(current).add(key));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the calendar.");
    } finally {
      loadingMonthsRef.current.delete(key);
    }
  }, [fetchRange, mergeAppointments]);

  useEffect(() => {
    if (view === "month") return;
    const controller = new AbortController();
    void Promise.resolve().then(async () => {
      setLoading(true);
      setError(null);
      try {
        setAppointments((await fetchRange(visibleRange, controller.signal)).sort((a, b) => a.starts_at.localeCompare(b.starts_at)));
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "Could not load the calendar.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    });
    return () => controller.abort();
  }, [fetchRange, view, visibleRange]);

  useEffect(() => {
    if (view !== "month") return;
    void Promise.resolve().then(() => {
      setLoading(false);
      setError(null);
      return Promise.all([-1, 0, 1].map(offset => loadMonth(addMonths(visibleMonth, offset))));
    });
  }, [loadMonth, view, visibleMonth]);

  const centerDateInMonthScroller = useCallback((date: Date, behavior: ScrollBehavior = "smooth") => {
    const container = monthScrollRef.current;
    if (!container) return;
    const monthSection = container.querySelector<HTMLElement>(`[data-month="${monthKey(date)}"]`);
    const week = monthSection?.querySelector<HTMLElement>(`[data-week="${dayKey(startOfWeek(date))}"]`);
    const target = week || monthSection;
    if (!target) return;
    container.scrollTo({ top: target.offsetTop - container.clientHeight / 2 + target.clientHeight / 2, behavior });
  }, []);

  useEffect(() => {
    if (view !== "month" || centeredMonthRef.current) return;
    centeredMonthRef.current = true;
    requestAnimationFrame(() => centerDateInMonthScroller(today, "auto"));
  }, [centerDateInMonthScroller, today, view]);

  useEffect(() => {
    if (!selectedDate) return;
    const dismissAgenda = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node) || agendaRef.current?.contains(target)) return;
      if (target instanceof Element && target.closest("[data-calendar-day]")) return;
      setSelectedDate(null);
    };
    document.addEventListener("pointerdown", dismissAgenda);
    return () => document.removeEventListener("pointerdown", dismissAgenda);
  }, [selectedDate]);

  const appointmentsByDay = useMemo(() => {
    const indexed = new Map<string, Appointment[]>();
    for (const appointment of appointments) {
      const key = dayKey(appointment.starts_at);
      indexed.set(key, [...(indexed.get(key) || []), appointment]);
    }
    return indexed;
  }, [appointments]);
  const itemsForDay = useCallback((day: Date) => appointmentsByDay.get(dayKey(day)) || [], [appointmentsByDay]);
  const agendaDate = selectedDate || lastAgendaDate;
  const selectedItems = agendaDate ? itemsForDay(agendaDate) : [];
  const activeSelectedItems = selectedItems.filter(item => item.status !== "cancelled");
  const todayKey = dayKey(today);

  const rangeLabel = useMemo(() => {
    if (view === "day") return longDateFormatter.format(anchorDate);
    if (view === "month") return monthFormatter.format(visibleMonth);
    const weekStart = startOfWeek(anchorDate);
    const weekEnd = addDays(weekStart, 6);
    return `${new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric" }).format(weekStart)} – ${new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric", year: "numeric" }).format(weekEnd)}`;
  }, [anchorDate, view, visibleMonth]);

  const move = (direction: -1 | 1) => {
    if (view === "month") {
      const target = addMonths(visibleMonth, direction);
      setVisibleMonth(target);
      centerDateInMonthScroller(target);
      return;
    }
    setAnchorDate(current => view === "day" ? addDays(current, direction) : addDays(current, direction * 7));
  };

  const goToToday = () => {
    setAnchorDate(today);
    setSelectedDate(null);
    if (view === "month") {
      setVisibleMonth(startOfMonth(today));
      centerDateInMonthScroller(today);
    }
  };

  const handleMonthScroll = () => {
    if (scrollFrameRef.current !== null) return;
    scrollFrameRef.current = requestAnimationFrame(() => {
      scrollFrameRef.current = null;
      const container = monthScrollRef.current;
      if (!container) return;
      const center = container.scrollTop + container.clientHeight / 2;
      const sections = Array.from(container.querySelectorAll<HTMLElement>("[data-month]"));
      const nearest = sections.reduce<HTMLElement | null>((best, section) => {
        if (!best) return section;
        const distance = Math.abs(section.offsetTop + section.offsetHeight / 2 - center);
        const bestDistance = Math.abs(best.offsetTop + best.offsetHeight / 2 - center);
        return distance < bestDistance ? section : best;
      }, null);
      if (!nearest?.dataset.month) return;
      const nextMonth = monthStack.find(month => monthKey(month) === nearest.dataset.month);
      if (nextMonth && monthKey(nextMonth) !== monthKey(visibleMonth)) setVisibleMonth(nextMonth);
    });
  };

  useEffect(() => () => {
    if (scrollFrameRef.current !== null) cancelAnimationFrame(scrollFrameRef.current);
  }, []);

  const changeView = (nextView: CalendarView) => {
    if (selectedDate) setAnchorDate(selectedDate);
    setSelectedDate(null);
    setView(nextView);
  };

  return (
    <main className={`calendar-shell mx-auto py-8 transition-[width] duration-200 ease-out motion-reduce:transition-none sm:py-12 ${view === "month" && selectedDate ? "calendar-shell--agenda" : ""}`}>
      <section aria-label={`${view[0].toUpperCase()}${view.slice(1)} appointment calendar`} className="overflow-hidden rounded-2xl border border-stone-300 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-300 bg-white px-3 py-3 sm:px-4">
          <div className="min-w-44">
            <p className="text-sm font-semibold text-stone-900">{rangeLabel}</p>
            {view === "month" && <p className="mt-0.5 text-xs text-stone-500">Select a day to review its agenda</p>}
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <ViewControls view={view} onViewChange={changeView} />
            <div className="flex gap-1 rounded-xl border border-stone-300 bg-stone-50 p-1">
              <button type="button" aria-label={`Previous ${view}`} onClick={() => move(-1)} className="cursor-grab rounded-lg px-3 py-1.5 text-sm font-semibold text-stone-600 transition-colors duration-200 hover:bg-stone-100 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Previous</button>
              <button type="button" onClick={goToToday} className="cursor-grab rounded-lg px-3 py-1.5 text-sm font-semibold text-stone-600 transition-colors duration-200 hover:bg-stone-100 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Today</button>
              <button type="button" aria-label={`Next ${view}`} onClick={() => move(1)} className="cursor-grab rounded-lg px-3 py-1.5 text-sm font-semibold text-stone-600 transition-colors duration-200 hover:bg-stone-100 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Next</button>
            </div>
          </div>
        </div>

        {error ? (
          <div role="alert" className="m-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
        ) : view !== "month" && loading ? (
          <div className="p-6"><LoadingSpinner label="Loading calendar…" /></div>
        ) : view === "day" ? (
          <div className="p-4 sm:p-6">
            <div className="flex items-baseline justify-between border-b border-stone-200 pb-3">
              <h2 className="text-sm font-semibold text-stone-900">{new Intl.DateTimeFormat("en-US", { weekday: "long" }).format(anchorDate)}</h2>
              <span className={`grid size-8 place-items-center rounded-full text-sm font-semibold ${dayKey(anchorDate) === todayKey ? "bg-emerald-800 text-white" : "text-stone-700"}`}>{anchorDate.getDate()}</span>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {itemsForDay(anchorDate).length ? itemsForDay(anchorDate).map(item => <AppointmentCard key={item.id} appointment={item} />) : <EmptyDay />}
            </div>
          </div>
        ) : view === "week" ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-7">
            {days.map(day => {
              const items = itemsForDay(day);
              const isToday = dayKey(day) === todayKey;
              return (
                <div key={day.toISOString()} className="min-h-44 border-b border-stone-200 p-3 sm:border-r lg:border-b-0 last:border-r-0">
                  <div className={`flex items-baseline justify-between ${isToday ? "text-emerald-800" : "text-stone-700"}`}>
                    <span className="text-xs font-semibold uppercase tracking-wide">{weekdayFormatter.format(day)}</span>
                    <span className={`grid size-7 place-items-center rounded-full text-sm font-semibold ${isToday ? "bg-emerald-800 text-white" : ""}`}>{day.getDate()}</span>
                  </div>
                  <div className="mt-3 space-y-2">{items.length ? items.map(item => <AppointmentCard key={item.id} appointment={item} />) : <EmptyDay />}</div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className={`grid ${agendaDate ? "calendar-month-layout--agenda" : ""} ${selectedDate ? "calendar-month-layout--agenda-open" : ""}`}>
            <div ref={monthScrollRef} onScroll={handleMonthScroll} className={`calendar-scroll-surface relative max-h-[72vh] min-h-[520px] overflow-auto overscroll-contain scroll-smooth border-stone-300 ${agendaDate ? "lg:border-r" : ""}`}>
              <div className="sticky top-0 z-20 grid min-w-[700px] grid-cols-7 border-b border-stone-300 bg-stone-50">
                {Array.from({ length: 7 }, (_, index) => addDays(startOfWeek(today), index)).map(day => (
                  <div key={day.toISOString()} className="border-r border-stone-200 px-2 py-2 text-center text-[11px] font-semibold uppercase tracking-wide text-stone-600 last:border-r-0">{weekdayFormatter.format(day)}</div>
                ))}
              </div>
              <div aria-hidden="true" className="calendar-scroll-fade pointer-events-none sticky top-[33px] z-10 -mb-5 h-5 min-w-[700px]" />
              <div className="min-w-[700px]">
                {monthStack.map(month => (
                  <section key={monthKey(month)} data-month={monthKey(month)} aria-label={monthFormatter.format(month)} className="border-b border-stone-300 last:border-b-0">
                    <h2 className="bg-white px-4 pb-2 pt-5 text-base font-semibold text-stone-900">{monthFormatter.format(month)}</h2>
                    {(monthWeeks.get(monthKey(month)) || []).map(week => {
                      const weekStartKey = dayKey(week[0]);
                      const isCurrentWeek = weekStartKey === dayKey(startOfWeek(today));
                      return (
                        <div key={weekStartKey} data-week={weekStartKey} className={`grid grid-cols-7 border-t border-stone-200 ${isCurrentWeek ? "bg-emerald-50" : ""}`}>
                          {week.map(day => {
                            const inMonth = day.getMonth() === month.getMonth();
                            if (!inMonth) return <div key={day.toISOString()} aria-hidden="true" className="aspect-square border-r border-stone-200 bg-stone-50 last:border-r-0" />;
                            const items = itemsForDay(day);
                            const activeItems = items.filter(item => item.status !== "cancelled");
                            const isToday = dayKey(day) === todayKey;
                            const isSelected = selectedDate ? dayKey(day) === dayKey(selectedDate) : false;
                            return (
                              <button
                                key={day.toISOString()}
                                type="button"
                                data-calendar-day
                                onClick={() => {
                                  if (selectedDate && dayKey(selectedDate) === dayKey(day)) {
                                    setSelectedDate(null);
                                    return;
                                  }
                                  setLastAgendaDate(day);
                                  setSelectedDate(day);
                                }}
                                aria-label={`${longDateFormatter.format(day)}, ${activeItems.length} ${activeItems.length === 1 ? "meeting" : "meetings"}`}
                                aria-pressed={isSelected}
                                className={`relative aspect-square cursor-grab border-r border-stone-200 p-2 pt-7 text-left transition-colors duration-200 ease-out last:border-r-0 motion-reduce:transition-none active:cursor-grabbing focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-emerald-700 ${isSelected ? "bg-emerald-50 shadow-[inset_0_0_0_1px_var(--accent-strong)]" : "hover:bg-stone-50"}`}
                              >
                                <span className={`absolute left-1.5 top-1.5 grid size-5 place-items-center rounded-full text-[11px] font-semibold ${isToday ? "bg-emerald-800 text-white" : "text-stone-600"}`}>{day.getDate()}</span>
                                {activeItems.length > 0 && <span className="absolute right-1.5 top-1.5 rounded-full border border-emerald-300 bg-emerald-50 px-1.5 py-0.5 text-[10px] font-bold text-emerald-900">{activeItems.length}</span>}
                                <span className="block space-y-1">
                                  {items.slice(0, 2).map(item => (
                                    <span key={item.id} className={`block truncate text-[10px] leading-4 ${item.status === "cancelled" ? "text-stone-500 line-through" : "text-stone-700"}`}>
                                      <strong className="font-semibold">{timeFormatter.format(new Date(item.starts_at))}</strong> {item.client_name || "Client"}
                                    </span>
                                  ))}
                                  {items.length > 2 && <span className="block text-[10px] font-semibold text-stone-500">+{items.length - 2} more</span>}
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      );
                    })}
                  </section>
                ))}
              </div>
            </div>

            {agendaDate && <aside ref={agendaRef} aria-label="Selected day agenda" aria-hidden={!selectedDate} className={`calendar-day-agenda border-t border-stone-300 bg-stone-50 p-4 lg:border-t-0 ${selectedDate ? "calendar-day-agenda--open" : "calendar-day-agenda--closed"}`}>
              <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">Day agenda</p>
              <h2 className="mt-1 text-base font-semibold text-stone-900">{longDateFormatter.format(agendaDate)}</h2>
              <p className="mt-1 text-sm text-stone-600">
                {activeSelectedItems.length} {activeSelectedItems.length === 1 ? "meeting" : "meetings"}
                {selectedItems.length > activeSelectedItems.length ? ` · ${selectedItems.length - activeSelectedItems.length} cancelled` : ""}
              </p>
              <div className="mt-4 space-y-2">
                {!loadedMonths.has(monthKey(agendaDate)) ? <LoadingSpinner label="Loading day agenda…" /> : selectedItems.length ? selectedItems.map(item => <AppointmentCard key={item.id} appointment={item} />) : <EmptyDay />}
              </div>
            </aside>}
          </div>
        )}
      </section>
    </main>
  );
}
