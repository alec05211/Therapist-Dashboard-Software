type TimeRange = { starts_at: string; ends_at: string };

// Thirty minutes is the shortest supported scheduling duration. Keep an exact
// thirty-minute gap open, but absorb shorter gaps into the unavailable region.
export function mergeReservedTimes(ranges: TimeRange[]): TimeRange[] {
  const sorted = ranges.map(range => ({ ...range })).sort((a, b) =>
    Date.parse(a.starts_at) - Date.parse(b.starts_at));
  const merged: TimeRange[] = [];
  for (const range of sorted) {
    const previous = merged[merged.length - 1];
    if (previous && Date.parse(range.starts_at) - Date.parse(previous.ends_at) < 30 * 60_000) {
      if (Date.parse(range.ends_at) > Date.parse(previous.ends_at)) previous.ends_at = range.ends_at;
    } else {
      merged.push(range);
    }
  }
  return merged;
}
