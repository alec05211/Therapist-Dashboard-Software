from datetime import datetime, timedelta
import unittest

from database.scheduling import available_recurring_slots, recurring_occurrences


class SchedulingTests(unittest.TestCase):
    def test_recurring_occurrences_honor_cadence(self):
        start = datetime.fromisoformat("2026-09-28T15:00:00-04:00")
        self.assertEqual(recurring_occurrences(start, 2, 3)[2], start + timedelta(weeks=4))

    def test_suggestions_exclude_conflicts_anywhere_in_series(self):
        now = datetime.fromisoformat("2026-09-25T12:00:00-04:00")
        busy = [{
            "starts_at": datetime.fromisoformat("2026-10-05T09:00:00-04:00"),
            "ends_at": datetime.fromisoformat("2026-10-05T10:00:00-04:00"),
            "status": "scheduled",
        }]
        slots = available_recurring_slots(busy, timezone="America/New_York", duration_minutes=50,
                                           cadence_weeks=1, occurrences=8, now=now)
        self.assertNotIn("2026-09-28T09:00:00-04:00", [slot["starts_at"] for slot in slots])


if __name__ == "__main__":
    unittest.main()
