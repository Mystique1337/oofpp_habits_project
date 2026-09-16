"""Tests for `Habit`, `Completion` and `Periodicity`.

The streak tests are the heart of the suite, so they build their check-offs
explicitly from a fixed date rather than reusing the seed fixture: when one
fails, the pattern that broke it is visible in the test itself.
"""

import unittest
from datetime import date, datetime, time, timedelta

from models.completion import Completion
from models.habit import Habit
from models.periodicity import Periodicity

MONDAY = date(2026, 3, 2)
WEDNESDAY = date(2026, 3, 4)


def days_before(anchor: date, *offsets: int) -> list[datetime]:
    """Timestamps for the given numbers of days before `anchor`."""
    return [datetime.combine(anchor - timedelta(days=n), time(9, 0)) for n in offsets]


def habit_completed_on(periodicity: str, moments: list) -> Habit:
    """A habit already checked off at each of `moments`."""
    habit = Habit("Test Habit", "for the suite", periodicity)
    for moment in moments:
        habit.check_off(moment)
    return habit


class CompletionTests(unittest.TestCase):
    """A completion is a validated, serialisable timestamp."""

    def test_at_splits_a_datetime_into_iso_date_and_time(self):
        completion = Completion.at(datetime(2026, 1, 2, 7, 15, 30))
        self.assertEqual(completion.date, "2026-01-02")
        self.assertEqual(completion.time, "07:15:30")

    def test_typed_properties_round_trip(self):
        completion = Completion.at(datetime(2026, 1, 2, 7, 15, 30))
        self.assertEqual(completion.as_date, date(2026, 1, 2))
        self.assertEqual(completion.as_time, time(7, 15, 30))

    def test_serialisation_round_trip(self):
        original = Completion.at(datetime(2026, 1, 2, 7, 15, 30))
        self.assertEqual(Completion.from_dict(original.to_dict()), original)

    def test_a_malformed_date_is_rejected_on_construction(self):
        with self.assertRaises(ValueError):
            Completion(date="02/01/2026", time="07:15:00")

    def test_a_malformed_time_is_rejected_on_construction(self):
        with self.assertRaises(ValueError):
            Completion(date="2026-01-02", time="quarter past seven")


class PeriodicityTests(unittest.TestCase):
    """Period indices are what make a streak a run of consecutive integers."""

    def test_parse_accepts_mixed_case_and_padding(self):
        self.assertIs(Periodicity.parse("  Weekly "), Periodicity.WEEKLY)

    def test_parse_is_idempotent(self):
        self.assertIs(Periodicity.parse(Periodicity.DAILY), Periodicity.DAILY)

    def test_parse_rejects_an_unsupported_period(self):
        with self.assertRaises(ValueError):
            Periodicity.parse("fortnightly")

    def test_consecutive_days_get_consecutive_indices(self):
        index = Periodicity.DAILY.period_index
        self.assertEqual(index(MONDAY + timedelta(days=1)), index(MONDAY) + 1)

    def test_every_day_of_one_week_shares_a_weekly_index(self):
        index = Periodicity.WEEKLY.period_index
        indices = {index(MONDAY + timedelta(days=n)) for n in range(7)}
        self.assertEqual(len(indices), 1)

    def test_sunday_and_the_next_monday_are_different_weeks(self):
        index = Periodicity.WEEKLY.period_index
        sunday = MONDAY + timedelta(days=6)
        self.assertEqual(index(sunday + timedelta(days=1)), index(sunday) + 1)


class HabitCreationTests(unittest.TestCase):
    """Creating a habit validates its definition."""

    def test_a_new_habit_starts_with_no_completions(self):
        habit = Habit("Read", "20 pages", "daily")
        self.assertEqual(habit.completions, [])
        self.assertEqual(habit.longest_streak(), 0)

    def test_the_name_is_stripped(self):
        self.assertEqual(Habit("  Read  ", periodicity="daily").name, "Read")

    def test_a_blank_name_is_rejected(self):
        with self.assertRaises(ValueError):
            Habit("   ", "nothing", "daily")

    def test_an_unsupported_periodicity_is_rejected(self):
        with self.assertRaises(ValueError):
            Habit("Read", "20 pages", "hourly")

    def test_the_periodicity_string_is_converted_to_the_enum(self):
        self.assertIs(Habit("Read", periodicity="weekly").periodicity, Periodicity.WEEKLY)

    def test_creation_time_is_recorded(self):
        made_at = datetime(2026, 1, 1, 8, 0)
        self.assertEqual(Habit("Read", periodicity="daily", created_at=made_at).created_at, made_at)


class HabitEditTests(unittest.TestCase):
    """Editing changes the definition and leaves the event log alone."""

    def setUp(self):
        # Anchored mid-week so all three days fall inside one ISO week, which is
        # what makes the periodicity-change test below read as 3 days = 1 week.
        self.habit = habit_completed_on("daily", days_before(WEDNESDAY, 0, 1, 2))

    def test_the_name_can_be_changed(self):
        self.habit.edit(name="Read More")
        self.assertEqual(self.habit.name, "Read More")

    def test_the_description_can_be_changed(self):
        self.habit.edit(description="30 pages")
        self.assertEqual(self.habit.description, "30 pages")

    def test_omitted_fields_are_left_alone(self):
        self.habit.edit(description="30 pages")
        self.assertEqual(self.habit.name, "Test Habit")
        self.assertIs(self.habit.periodicity, Periodicity.DAILY)

    def test_editing_keeps_the_completion_history(self):
        self.habit.edit(name="Renamed", periodicity="weekly")
        self.assertEqual(len(self.habit.completions), 3)

    def test_changing_the_periodicity_re_reads_the_same_history(self):
        self.assertEqual(self.habit.longest_streak(), 3)
        self.habit.edit(periodicity="weekly")
        self.assertEqual(self.habit.longest_streak(), 1)

    def test_a_blank_new_name_is_rejected(self):
        with self.assertRaises(ValueError):
            self.habit.edit(name="  ")

    def test_an_unsupported_new_periodicity_is_rejected(self):
        with self.assertRaises(ValueError):
            self.habit.edit(periodicity="yearly")


class CheckOffTests(unittest.TestCase):
    """Checking off appends to the event log."""

    def test_check_off_appends_a_completion(self):
        habit = Habit("Read", periodicity="daily")
        habit.check_off(datetime(2026, 3, 2, 9, 0))
        self.assertEqual(habit.completion_dates(), [date(2026, 3, 2)])

    def test_completions_stay_in_chronological_order(self):
        habit = habit_completed_on("daily", days_before(MONDAY, 0, 5, 2))
        self.assertEqual(habit.completion_dates(), sorted(habit.completion_dates()))

    def test_is_completed_on_sees_the_same_day(self):
        habit = habit_completed_on("daily", days_before(MONDAY, 0))
        self.assertTrue(habit.is_completed_on(MONDAY))
        self.assertFalse(habit.is_completed_on(MONDAY - timedelta(days=1)))

    def test_is_completed_on_covers_the_whole_week_for_a_weekly_habit(self):
        habit = habit_completed_on("weekly", days_before(MONDAY, 0))
        self.assertTrue(habit.is_completed_on(MONDAY + timedelta(days=5)))


class DailyStreakTests(unittest.TestCase):
    """Daily streaks count consecutive calendar days."""

    def test_an_unused_habit_has_no_streak(self):
        habit = Habit("Read", periodicity="daily")
        self.assertEqual(habit.longest_streak(), 0)
        self.assertEqual(habit.current_streak(MONDAY), 0)

    def test_consecutive_days_build_a_streak(self):
        habit = habit_completed_on("daily", days_before(MONDAY, 0, 1, 2, 3))
        self.assertEqual(habit.longest_streak(), 4)
        self.assertEqual(habit.current_streak(MONDAY), 4)

    def test_a_gap_breaks_the_run_and_the_longest_run_wins(self):
        habit = habit_completed_on("daily", days_before(MONDAY, 0, 1, 3, 4, 5, 6))
        self.assertEqual(habit.longest_streak(), 4)
        self.assertEqual(habit.current_streak(MONDAY), 2)

    def test_two_check_offs_on_one_day_count_once(self):
        moments = [datetime(2026, 3, 2, 8, 0), datetime(2026, 3, 2, 20, 0)]
        habit = habit_completed_on("daily", moments)
        self.assertEqual(habit.longest_streak(), 1)

    def test_todays_task_is_not_yet_overdue(self):
        # Done yesterday, not yet today: the day is not over, so nothing is broken.
        habit = habit_completed_on("daily", days_before(MONDAY, 1, 2, 3))
        self.assertEqual(habit.current_streak(MONDAY), 3)
        self.assertFalse(habit.is_broken(MONDAY))

    def test_a_missed_day_breaks_the_current_streak(self):
        habit = habit_completed_on("daily", days_before(MONDAY, 2, 3, 4))
        self.assertEqual(habit.current_streak(MONDAY), 0)
        self.assertTrue(habit.is_broken(MONDAY))

    def test_a_broken_habit_keeps_its_record(self):
        habit = habit_completed_on("daily", days_before(MONDAY, 2, 3, 4))
        self.assertEqual(habit.longest_streak(), 3)


class WeeklyStreakTests(unittest.TestCase):
    """Weekly streaks count consecutive weeks, not consecutive days."""

    def test_seven_days_in_a_row_is_one_week_not_seven(self):
        habit = habit_completed_on("weekly", days_before(MONDAY + timedelta(days=6), *range(7)))
        self.assertEqual(habit.longest_streak(), 1)

    def test_consecutive_weeks_build_a_streak(self):
        moments = days_before(MONDAY, 0, 7, 14, 21)
        habit = habit_completed_on("weekly", moments)
        self.assertEqual(habit.longest_streak(), 4)
        self.assertEqual(habit.current_streak(MONDAY), 4)

    def test_a_skipped_week_breaks_the_run(self):
        habit = habit_completed_on("weekly", days_before(MONDAY, 0, 14, 21))
        self.assertEqual(habit.longest_streak(), 2)
        self.assertEqual(habit.current_streak(MONDAY), 1)

    def test_repeats_inside_one_week_do_not_inflate_the_streak(self):
        wednesday, friday = MONDAY + timedelta(days=2), MONDAY + timedelta(days=4)
        habit = habit_completed_on(
            "weekly",
            [datetime.combine(wednesday, time(9, 0)), datetime.combine(friday, time(9, 0))],
        )
        self.assertEqual(habit.longest_streak(), 1)

    def test_this_weeks_task_is_not_yet_overdue(self):
        habit = habit_completed_on("weekly", days_before(MONDAY, 7, 14))
        self.assertEqual(habit.current_streak(MONDAY), 2)

    def test_a_skipped_whole_week_breaks_the_current_streak(self):
        habit = habit_completed_on("weekly", days_before(MONDAY, 14, 21))
        self.assertEqual(habit.current_streak(MONDAY), 0)


class SerialisationTests(unittest.TestCase):
    """A habit survives a trip through the storage format intact."""

    def setUp(self):
        self.habit = habit_completed_on("weekly", days_before(MONDAY, 0, 7, 14))

    def test_round_trip_preserves_the_definition(self):
        restored = Habit.from_dict(self.habit.to_dict())
        self.assertEqual(restored.name, self.habit.name)
        self.assertEqual(restored.description, self.habit.description)
        self.assertIs(restored.periodicity, self.habit.periodicity)
        self.assertEqual(restored.created_at, self.habit.created_at)

    def test_round_trip_preserves_the_event_log(self):
        restored = Habit.from_dict(self.habit.to_dict())
        self.assertEqual(restored.completions, self.habit.completions)

    def test_round_trip_preserves_the_streaks(self):
        restored = Habit.from_dict(self.habit.to_dict())
        self.assertEqual(restored.longest_streak(), self.habit.longest_streak())

    def test_the_periodicity_is_stored_as_a_plain_string(self):
        self.assertEqual(self.habit.to_dict()["periodicity"], "weekly")

    def test_data_written_by_the_earlier_flat_version_still_loads(self):
        legacy = {
            "name": "Read",
            "description": "20 pages",
            "periodicity": "daily",
            "created_date": "2025-12-06T14:11:00",
            "completions": [{"date": "2025-12-06", "time": "14:11:00"}],
        }
        restored = Habit.from_dict(legacy)
        self.assertEqual(restored.created_at, datetime(2025, 12, 6, 14, 11))
        self.assertEqual(restored.longest_streak(), 1)

    def test_a_missing_required_field_is_reported(self):
        with self.assertRaises(KeyError):
            Habit.from_dict({"description": "no name here", "periodicity": "daily"})


if __name__ == "__main__":
    unittest.main()
