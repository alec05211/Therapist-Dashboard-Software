"""Scheduling helpers shared by the calendar and client-care settings."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


ACTIVE_STATUSES = ("scheduled", "confirmed")


def overlaps(start: datetime, end: datetime, appointments: list[dict]) -> bool:
    return any(
        row.get("status") in ACTIVE_STATUSES
        and row["starts_at"] < end
        and row["ends_at"] > start
        for row in appointments
    )


def recurring_occurrences(start: datetime, cadence_weeks: int, count: int) -> list[datetime]:
    if cadence_weeks not in (1, 2, 4):
        raise ValueError("Cadence must be weekly, every two weeks, or every four weeks.")
    return [start + timedelta(weeks=cadence_weeks * index) for index in range(count)]


def available_recurring_slots(
    appointments: list[dict], *, timezone: str, duration_minutes: int,
    cadence_weeks: int, occurrences: int = 8, limit: int = 12,
    now: datetime | None = None,
) -> list[dict]:
    """Return weekday 9–5 slots that remain free across the requested series."""
    zone = ZoneInfo(timezone)
    local_now = (now or datetime.now(zone)).astimezone(zone)
    first_day = local_now.date() + timedelta(days=1)
    suggestions: list[dict] = []
    for day_offset in range(21):
        day = first_day + timedelta(days=day_offset)
        if day.weekday() >= 5:
            continue
        for minute in range(9 * 60, 17 * 60 - duration_minutes + 1, 30):
            local_start = datetime.combine(day, time(minute // 60, minute % 60), zone)
            candidates = recurring_occurrences(local_start, cadence_weeks, occurrences)
            if any(overlaps(start, start + timedelta(minutes=duration_minutes), appointments) for start in candidates):
                continue
            suggestions.append({"starts_at": local_start.isoformat(), "weekday": day.weekday(), "local_time": local_start.strftime("%H:%M")})
            if len(suggestions) >= limit:
                return suggestions
    return suggestions
