from datetime import datetime, timedelta
import unittest
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from database.scheduling import available_recurring_slots, next_recurring_occurrence, recurring_occurrences
import server


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

    def test_recurring_horizon_preserves_local_time_across_dst(self):
        start = datetime.fromisoformat("2026-10-26T15:00:00-04:00")
        next_start = next_recurring_occurrence(start, 1, "America/New_York")
        self.assertEqual(next_start.isoformat(), "2026-11-02T15:00:00-05:00")

    def test_configured_schedule_replenishes_to_three_upcoming_sessions(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        latest = datetime.now(ZoneInfo("America/New_York")) - timedelta(weeks=1)
        cursor.fetchone.side_effect = [
            {'cadence_weeks': 1, 'duration_minutes': 50, 'meeting_mode': 'in_person',
             'timezone': 'America/New_York', 'preferred_weekday': 0,
             'preferred_start_local': latest.timetz().replace(tzinfo=None)},
            {'starts_at': latest, 'series_id': None},
            {'count': 0},
            None, None, None, None, None, None,
        ]
        inserted = server.ensure_recurring_schedule_horizon(
            connection, {'organization_id': 'org', 'client_id': 'client'},
            {'practitioner_id': 'practitioner'},
        )
        inserts = [call for call in cursor.execute.call_args_list if 'INSERT INTO app.appointments' in call.args[0]]
        self.assertEqual(inserted, 3)
        self.assertEqual(len(inserts), 3)


if __name__ == "__main__":
    unittest.main()
