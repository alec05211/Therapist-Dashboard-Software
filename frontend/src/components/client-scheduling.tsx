"use client";

import { useCallback, useEffect, useState } from "react";
import { ClientScheduleWeek } from "@/components/client-schedule-week";
import { LoadingSpinner } from "@/components/loading-spinner";
import { settingsFieldClass } from "@/components/settings-layout";
import type { Appointment } from "@/lib/types";

type Preferences = { cadence_weeks: 1 | 2 | 4; duration_minutes: number; meeting_mode: "in_person" | "video" | "phone"; timezone: string };
type RecurringDraft = { cadence_weeks: "" | 1 | 2 | 4; duration_minutes: "" | number; meeting_mode: "" | Preferences["meeting_mode"] };
type BusyTime = { starts_at: string; ends_at: string };
type Data = { organization_id: string; client_id: string; client_name: string; preferences: Preferences; appointments: Appointment[]; busy_times: BusyTime[]; has_existing_schedule: boolean; current_recurring_starts_at: string | null };

async function body(response: Response) {
  const value = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(value.detail || "Could not update the schedule.");
  return value as Data;
}

const localInput = (value: string) => {
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
};
const formatDate = (value: string) => new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
const formatTime = (date: Date) => new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(date).replace(":00", "");
const formatRecurringBlock = (value: string, durationMinutes: number) => {
  const start = new Date(value);
  const end = new Date(start.getTime() + durationMinutes * 60_000);
  const date = new Intl.DateTimeFormat("en-US", { weekday: "long", month: "short", day: "numeric" }).format(start);
  return `${date}, ${formatTime(start)} – ${formatTime(end)}`;
};

function overlaps(start: Date, end: Date, item: BusyTime) {
  return new Date(item.starts_at) < end && new Date(item.ends_at) > start;
}

function recurringSuggestions(data: Data, preferences: Preferences) {
  const active: BusyTime[] = [
    ...(data.busy_times || []),
    ...data.appointments.filter(item => item.status === "scheduled" || item.status === "confirmed").map(item => ({ starts_at: item.starts_at, ends_at: item.ends_at })),
  ];
  const now = new Date();
  const firstDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const suggestions: string[] = [];
  for (let dayOffset = 0; dayOffset < 21 && suggestions.length < 12; dayOffset += 1) {
    const day = new Date(firstDay);
    day.setDate(firstDay.getDate() + dayOffset);
    if (day.getDay() === 0 || day.getDay() === 6) continue;
    for (let minute = 9 * 60; minute + preferences.duration_minutes <= 17 * 60 && suggestions.length < 12; minute += 30) {
      const start = new Date(day);
      start.setHours(Math.floor(minute / 60), minute % 60, 0, 0);
      const seriesIsOpen = Array.from({ length: 8 }, (_, index) => {
        const occurrence = new Date(start);
        occurrence.setDate(start.getDate() + index * preferences.cadence_weeks * 7);
        const end = new Date(occurrence.getTime() + preferences.duration_minutes * 60_000);
        return !active.some(item => overlaps(occurrence, end, item));
      }).every(Boolean);
      if (seriesIsOpen) suggestions.push(start.toISOString());
    }
  }
  return suggestions;
}

function Chevron({ expanded }: { expanded: boolean }) {
  return <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className={`size-4 transition-transform duration-200 motion-reduce:transition-none ${expanded ? "rotate-180" : ""}`}><path d="m5 7.5 5 5 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

export function ClientScheduling({ clientId, initiallyExpanded = false, onChanged }: { clientId?: string; initiallyExpanded?: boolean; onChanged?: () => void }) {
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [recurringOpen, setRecurringOpen] = useState(initiallyExpanded);
  const [recurringStart, setRecurringStart] = useState("");
  const [recurringDraft, setRecurringDraft] = useState<RecurringDraft>({ cadence_weeks: "", duration_minutes: "", meeting_mode: "" });
  const [rescheduling, setRescheduling] = useState<string | null>(null);
  const [rescheduleStart, setRescheduleStart] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const loaded = await body(await fetch(`/api/client-scheduling${clientId ? `?client_id=${encodeURIComponent(clientId)}` : ""}`, { cache: "no-store" }));
      setData(loaded);
      setRecurringDraft(loaded.has_existing_schedule ? { cadence_weeks: loaded.preferences.cadence_weeks, duration_minutes: loaded.preferences.duration_minutes, meeting_mode: loaded.preferences.meeting_mode } : { cadence_weeks: "", duration_minutes: "", meeting_mode: "" });
      setRecurringStart(loaded.current_recurring_starts_at || "");
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load scheduling settings."); }
    finally { setLoading(false); }
  }, [clientId]);
  useEffect(() => { void Promise.resolve().then(load); }, [load]);

  const mutate = async (url: string, method: string, payload: object, success: string) => {
    if (!data || busy) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      setData(await body(await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ organization_id: data.organization_id, client_id: data.client_id, ...payload }) })));
      setMessage(success); onChanged?.();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update the schedule."); }
    finally { setBusy(false); }
  };

  if (loading) return <LoadingSpinner label="Loading scheduling settings…" />;
  if (!data) return <p role="alert" className="mt-5 text-sm text-red-700">{error || "Scheduling is unavailable."}</p>;

  const future = data.appointments.filter(item => new Date(item.starts_at) > new Date()).sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  const configuredPreferences = recurringDraft.cadence_weeks && recurringDraft.duration_minutes && recurringDraft.meeting_mode ? { ...data.preferences, cadence_weeks: recurringDraft.cadence_weeks, duration_minutes: recurringDraft.duration_minutes, meeting_mode: recurringDraft.meeting_mode } as Preferences : null;
  const suggestions = configuredPreferences ? recurringSuggestions(data, configuredPreferences) : [];
  const recurringOptions = data.current_recurring_starts_at && !suggestions.includes(data.current_recurring_starts_at) ? [data.current_recurring_starts_at, ...suggestions] : suggestions;
  const updateRecurringDraft = (draft: RecurringDraft) => { setRecurringStart(""); setRecurringDraft(draft); };

  return <div className="mt-5 space-y-6 text-left">
    <section className="overflow-hidden rounded-xl border border-stone-300 bg-stone-50">
      <button type="button" aria-expanded={recurringOpen} onClick={() => setRecurringOpen(current => !current)} className="flex w-full cursor-grab items-center justify-between gap-3 px-4 py-3.5 text-left text-sm font-semibold text-stone-900 hover:bg-stone-100 active:cursor-grabbing">
        Configure Recurring Appointment
        <Chevron expanded={recurringOpen} />
      </button>
      {recurringOpen ? <div className="border-t border-stone-300 p-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-xs font-semibold text-stone-700">Frequency<select value={recurringDraft.cadence_weeks} onChange={event => updateRecurringDraft({ ...recurringDraft, cadence_weeks: Number(event.target.value) as 1 | 2 | 4 })} className={settingsFieldClass}><option value="" disabled>Select frequency</option><option value="1">Weekly</option><option value="2">Every 2 weeks</option><option value="4">Every 4 weeks</option></select></label>
          <label className="text-xs font-semibold text-stone-700">Length<select value={recurringDraft.duration_minutes} onChange={event => updateRecurringDraft({ ...recurringDraft, duration_minutes: Number(event.target.value) })} className={settingsFieldClass}><option value="" disabled>Select length</option>{[30, 45, 50, 60, 75, 90].map(value => <option key={value} value={value}>{value} minutes</option>)}</select></label>
          <label className="text-xs font-semibold text-stone-700">Format<select value={recurringDraft.meeting_mode} onChange={event => updateRecurringDraft({ ...recurringDraft, meeting_mode: event.target.value as Preferences["meeting_mode"] })} className={settingsFieldClass}><option value="" disabled>Select format</option><option value="in_person">In person</option><option value="video">Video</option><option value="phone">Phone</option></select></label>
        </div>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <label className="min-w-72 flex-1 text-xs font-semibold text-stone-700">Available recurring time<select value={recurringStart} disabled={!configuredPreferences} onChange={event => setRecurringStart(event.target.value)} className={settingsFieldClass}><option value="" disabled>Select an available time</option>{recurringOptions.map(startsAt => <option key={startsAt} value={startsAt}>{formatRecurringBlock(startsAt, configuredPreferences?.duration_minutes || data.preferences.duration_minutes)}{startsAt === data.current_recurring_starts_at ? " (current)" : ""}</option>)}</select></label>
          <button disabled={!configuredPreferences || !recurringStart || recurringStart === data.current_recurring_starts_at || busy} onClick={() => configuredPreferences && void mutate("/api/client-scheduling/appointments", "POST", { ...configuredPreferences, starts_at: recurringStart, appointment_type: "recurring", recurrence_count: 8 }, "Eight recurring appointments scheduled.").then(() => setRecurringStart(""))} className="cursor-grab rounded-xl bg-emerald-800 px-3.5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-900 active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-50">{recurringStart === data.current_recurring_starts_at && recurringStart ? "Current schedule" : "Schedule series"}</button>
        </div>
      </div> : null}
    </section>

    <ClientScheduleWeek appointments={data.appointments} busyTimes={data.busy_times || []} busy={busy} durationMinutes={data.preferences.duration_minutes} onCreate={async (startsAt, appointmentType) => { await mutate("/api/client-scheduling/appointments", "POST", { ...data.preferences, starts_at: startsAt.toISOString(), appointment_type: appointmentType, recurrence_count: 1 }, "Session scheduled."); }} onReschedule={async (appointment, startsAt) => { await mutate(`/api/client-scheduling/appointments/${appointment.id}`, "PATCH", { action: "reschedule", starts_at: startsAt.toISOString(), duration_minutes: Math.round((new Date(appointment.ends_at).getTime() - new Date(appointment.starts_at).getTime()) / 60_000) }, "Session rescheduled."); }} onCancel={async appointment => { if (window.confirm(`Cancel the session on ${formatDate(appointment.starts_at)}?`)) await mutate(`/api/client-scheduling/appointments/${appointment.id}`, "PATCH", { action: "cancel", duration_minutes: data.preferences.duration_minutes }, "Session cancelled."); }} />

    <section><h4 className="font-semibold text-stone-900">Upcoming sessions</h4>{future.length ? <ul className="mt-3 divide-y divide-stone-200 overflow-hidden rounded-xl border border-stone-200">{future.map(item => <li key={item.id} className={`p-4 ${item.status === "cancelled" ? "bg-stone-50 opacity-60" : "bg-white"}`}><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm font-semibold text-stone-900">{formatDate(item.starts_at)}</p><p className="mt-1 text-xs capitalize text-stone-500">{item.appointment_type.replace("_", "-")} · {item.meeting_mode.replace("_", " ")} · {item.status}</p></div>{item.status !== "cancelled" && <div className="flex gap-2"><button onClick={() => { setRescheduling(item.id); setRescheduleStart(localInput(item.starts_at)); }} className="cursor-grab rounded-lg border border-stone-300 px-3 py-1.5 text-xs font-semibold text-stone-700 hover:bg-stone-100 active:cursor-grabbing">Reschedule</button><button disabled={busy} onClick={() => void mutate(`/api/client-scheduling/appointments/${item.id}`, "PATCH", { action: "cancel", duration_minutes: data.preferences.duration_minutes }, "Session cancelled.")} className="cursor-grab rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50 active:cursor-grabbing">Cancel</button></div>}</div>{rescheduling === item.id && <div className="mt-3 flex gap-2"><input type="datetime-local" value={rescheduleStart} onChange={event => setRescheduleStart(event.target.value)} className={`${settingsFieldClass} mt-0`} /><button disabled={!rescheduleStart || busy} onClick={() => void mutate(`/api/client-scheduling/appointments/${item.id}`, "PATCH", { action: "reschedule", starts_at: new Date(rescheduleStart).toISOString(), duration_minutes: data.preferences.duration_minutes }, "Session rescheduled.")} className="cursor-grab rounded-lg bg-emerald-800 px-3 text-xs font-semibold text-white active:cursor-grabbing">Save</button><button onClick={() => setRescheduling(null)} className="cursor-grab px-2 text-xs font-semibold text-stone-600 active:cursor-grabbing">Close</button></div>}</li>)}</ul> : <p className="mt-2 text-sm text-stone-600">No upcoming sessions yet.</p>}</section>
    {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
    {message ? <p role="status" className="text-sm font-medium text-emerald-800">{message}</p> : null}
  </div>;
}
