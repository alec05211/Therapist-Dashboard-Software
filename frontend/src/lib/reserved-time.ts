type TimeRange = { starts_at: string; ends_at: string };

// Keep gaps that fit this client’s session length open; absorb shorter gaps
// into the unavailable region without changing the underlying reservations.
export function mergeReservedTimes(ranges: TimeRange[], durationMinutes: number): TimeRange[] {
  const sorted = ranges.map(range => ({ ...range })).sort((a, b) =>
    Date.parse(a.starts_at) - Date.parse(b.starts_at));
  const merged: TimeRange[] = [];
  for (const range of sorted) {
    const previous = merged[merged.length - 1];
    if (previous && Date.parse(range.starts_at) - Date.parse(previous.ends_at) < durationMinutes * 60_000) {
      if (Date.parse(range.ends_at) > Date.parse(previous.ends_at)) previous.ends_at = range.ends_at;
    } else {
      merged.push(range);
    }
  }
  return merged;
}

// Client appointments still participate in gap calculations, but only their
// cards should be visible. Remove their occupied spans from the gray layer.
export function subtractReservedTimes(ranges: TimeRange[], appointments: TimeRange[]): TimeRange[] {
  return appointments.reduce((remaining, appointment) => remaining.flatMap(range => {
    const start = Date.parse(range.starts_at);
    const end = Date.parse(range.ends_at);
    const appointmentStart = Date.parse(appointment.starts_at);
    const appointmentEnd = Date.parse(appointment.ends_at);
    if (appointmentStart >= end || appointmentEnd <= start) return [range];
    return [
      ...(start < appointmentStart ? [{ starts_at: range.starts_at, ends_at: appointment.starts_at }] : []),
      ...(end > appointmentEnd ? [{ starts_at: appointment.ends_at, ends_at: range.ends_at }] : []),
    ];
  }), ranges);
}
