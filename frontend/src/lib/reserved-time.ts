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
