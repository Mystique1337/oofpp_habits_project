"""Tests for the CLI.

The menu is driven by feeding it a scripted list of keystrokes and capturing
what it prints, so these are real end-to-end runs: input goes in at the prompt
and the assertions are made against the data file afterwards.

They exist to catch the things unit tests on the domain cannot see, namely that
a menu number is wired to the action its label promises, and that bad input is
answered with a message instead of a traceback.
"""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from cli import interface
from fixtures.seed_data import build_seed_habits
from models.tracker import HabitTracker
from storage.json_storage import JsonStorage
from tests import FIXED_END_DATE

EXIT = str(len(interface.MENU) + 1)


class CliTestCase(unittest.TestCase):
    """Base case that runs the menu against a tracker on a throwaway file."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.data_file = Path(self.directory.name) / "habits.json"
        self.storage = JsonStorage(self.data_file)

    def seeded(self) -> HabitTracker:
        """A tracker holding the four-week fixture, ending today.

        The menu reads the real clock, so the data has to end today for the
        streak assertions below to mean anything. The fixture is built to hold
        its expected streaks whatever weekday it ends on, which is what makes
        that safe; `tests.test_analytics` pins the weekday and proves it.
        """
        return HabitTracker(storage=self.storage, habits=build_seed_habits())

    def empty(self) -> HabitTracker:
        """A tracker with no habits."""
        return HabitTracker(storage=self.storage, habits=[])

    def drive(self, tracker: HabitTracker, *keystrokes: str) -> str:
        """Run the menu against `tracker`, feeding it `keystrokes`, and capture output.

        An `Exit` keystroke is appended so the loop always terminates.
        """
        script = list(keystrokes) + [EXIT]
        buffer = io.StringIO()
        with patch("builtins.input", side_effect=script), redirect_stdout(buffer):
            interface.run(tracker)
        return buffer.getvalue()


class MenuTests(CliTestCase):
    """The menu renders and exits cleanly."""

    def test_every_action_is_listed(self):
        output = self.drive(self.empty())
        for label, _action in interface.MENU:
            self.assertIn(label, output)

    def test_the_exit_option_is_numbered_after_the_last_action(self):
        self.assertIn(f"{EXIT}. Exit", self.drive(self.empty()))

    def test_exiting_says_goodbye(self):
        self.assertIn("Goodbye", self.drive(self.empty()))

    def test_quit_also_exits(self):
        buffer = io.StringIO()
        with patch("builtins.input", side_effect=["quit"]), redirect_stdout(buffer):
            interface.run(self.empty())
        self.assertIn("Goodbye", buffer.getvalue())

    def test_a_non_numeric_choice_is_answered_not_raised(self):
        output = self.drive(self.empty(), "banana")
        self.assertIn(f"Enter a number between 1 and {EXIT}", output)

    def test_an_out_of_range_choice_is_answered(self):
        output = self.drive(self.empty(), "99")
        self.assertIn(f"Enter a number between 1 and {EXIT}", output)

    def test_a_closed_input_stream_exits_instead_of_raising(self):
        buffer = io.StringIO()
        with patch("builtins.input", side_effect=EOFError), redirect_stdout(buffer):
            interface.run(self.empty())
        self.assertIn("Goodbye", buffer.getvalue())


class CreateFlowTests(CliTestCase):
    """Menu option 1 creates a habit."""

    def test_a_habit_is_created_and_saved(self):
        tracker = self.empty()
        self.drive(tracker, "1", "Stretch", "10 minutes", "daily")
        self.assertEqual([h.name for h in self.storage.load()], ["Stretch"])

    def test_the_chosen_periodicity_is_applied(self):
        tracker = self.empty()
        self.drive(tracker, "1", "Groceries", "weekly shop", "weekly")
        self.assertEqual(str(tracker.require_habit("Groceries").periodicity), "weekly")

    def test_an_invalid_periodicity_is_re_prompted(self):
        tracker = self.empty()
        output = self.drive(tracker, "1", "Stretch", "10 minutes", "hourly", "daily")
        self.assertIn("Unknown periodicity", output)
        self.assertEqual(len(tracker), 1)

    def test_a_duplicate_name_is_refused_with_a_message(self):
        tracker = self.seeded()
        output = self.drive(tracker, "1", "Read", "again", "daily")
        self.assertIn("already exists", output)
        self.assertEqual(len(tracker), 5)

    def test_a_blank_name_twice_cancels_the_action(self):
        tracker = self.empty()
        self.drive(tracker, "1", "", "")
        self.assertEqual(len(tracker), 0)


class CheckOffFlowTests(CliTestCase):
    """Menu option 2 records a completion."""

    def test_a_check_off_is_recorded_and_saved(self):
        tracker = self.seeded()
        before = len(tracker.require_habit("Read").completions)
        self.drive(tracker, "2", "Read")
        self.assertEqual(len(tracker.require_habit("Read").completions), before + 1)
        self.assertEqual(
            len(self.storage.load()[1].completions),
            before + 1,
        )

    def test_an_unknown_habit_is_reported(self):
        output = self.drive(self.seeded(), "2", "Nothing")
        self.assertIn("No habit named", output)

    def test_a_second_check_off_in_the_same_period_says_so(self):
        tracker = self.empty()
        tracker.create_habit("Stretch", "10 minutes", "daily")
        tracker.check_off("Stretch")
        output = self.drive(tracker, "2", "Stretch")
        self.assertIn("streak is unchanged", output)


class ViewFlowTests(CliTestCase):
    """Menu options 3 to 5 list habits."""

    def test_option_three_lists_every_habit(self):
        output = self.drive(self.seeded(), "3")
        for name in ("Morning Exercise", "Read", "Meditate", "Weekly Review", "Team Meeting"):
            self.assertIn(name, output)

    def test_option_four_lists_only_daily_habits(self):
        output = self.drive(self.seeded(), "4")
        section = output.split("-- Daily habits --")[1].split("=====")[0]
        self.assertIn("Morning Exercise", section)
        self.assertNotIn("Weekly Review", section)

    def test_option_five_lists_only_weekly_habits(self):
        output = self.drive(self.seeded(), "5")
        section = output.split("-- Weekly habits --")[1].split("=====")[0]
        self.assertIn("Weekly Review", section)
        self.assertNotIn("Morning Exercise", section)

    def test_an_empty_tracker_says_so_rather_than_printing_nothing(self):
        self.assertIn("No habits yet", self.drive(self.empty(), "3"))


class AnalyticsFlowTests(CliTestCase):
    """Menu options 6 to 9 surface the analytics module."""

    def test_option_six_reports_both_streaks_for_one_habit(self):
        output = self.drive(self.seeded(), "6", "Meditate")
        self.assertIn("longest run 11 days", output)
        self.assertIn("current run 0 days", output)

    def test_option_six_reports_an_unknown_habit(self):
        self.assertIn("No habit named", self.drive(self.seeded(), "6", "Nothing"))

    def test_option_seven_names_the_record_holder(self):
        output = self.drive(self.seeded(), "7")
        self.assertIn("Morning Exercise", output)
        self.assertIn("28", output)

    def test_option_seven_handles_an_empty_tracker(self):
        self.assertIn("No habits yet", self.drive(self.empty(), "7"))

    def test_option_eight_shows_the_statistics_summary(self):
        output = self.drive(self.seeded(), "8")
        self.assertIn("Tracking 5 habits", output)
        self.assertIn("3 daily, 2 weekly", output)

    def test_option_eight_flags_the_lapsed_habit_and_only_that_one(self):
        output = self.drive(self.seeded(), "8")
        rows = [line for line in output.splitlines() if "check-offs" in line]
        broken = [line.split()[0] for line in rows if "broken" in line]
        self.assertEqual(broken, ["Meditate"])

    def test_option_eight_shows_a_live_streak_for_an_unbroken_habit(self):
        output = self.drive(self.seeded(), "8")
        row = next(line for line in output.splitlines() if "Morning Exercise" in line and "check-offs" in line)
        self.assertIn("(on 28)", row)

    def test_option_nine_ranks_the_hardest_habits(self):
        output = self.drive(self.seeded(), "9")
        ranked = [line for line in output.splitlines() if "completed" in line]
        self.assertIn("Meditate", ranked[0])
        self.assertNotIn("Morning Exercise", " ".join(ranked))


class EditFlowTests(CliTestCase):
    """Menu option 10 edits a habit."""

    def test_the_name_can_be_changed_leaving_other_fields_blank(self):
        tracker = self.seeded()
        self.drive(tracker, "10", "Read", "Read More", "", "")
        self.assertIsNotNone(tracker.get_habit("Read More"))

    def test_the_history_survives_an_edit(self):
        tracker = self.seeded()
        before = len(tracker.require_habit("Read").completions)
        self.drive(tracker, "10", "Read", "Read More", "", "")
        self.assertEqual(len(tracker.require_habit("Read More").completions), before)

    def test_the_edit_is_saved(self):
        self.drive(self.seeded(), "10", "Read", "Read More", "", "")
        self.assertIn("Read More", [h.name for h in self.storage.load()])

    def test_an_unknown_habit_is_reported(self):
        self.assertIn("No habit named", self.drive(self.seeded(), "10", "Nothing"))

    def test_renaming_onto_an_existing_habit_is_refused(self):
        tracker = self.seeded()
        output = self.drive(tracker, "10", "Read", "Meditate", "", "")
        self.assertIn("already exists", output)
        self.assertIsNotNone(tracker.get_habit("Read"))


class DeleteFlowTests(CliTestCase):
    """Menu option 11 deletes a habit, after confirming."""

    def test_confirming_removes_the_habit(self):
        tracker = self.seeded()
        self.drive(tracker, "11", "Read", "y")
        self.assertIsNone(tracker.get_habit("Read"))

    def test_the_deletion_is_saved(self):
        self.drive(self.seeded(), "11", "Read", "y")
        self.assertNotIn("Read", [h.name for h in self.storage.load()])

    def test_declining_keeps_the_habit(self):
        tracker = self.seeded()
        self.drive(tracker, "11", "Read", "n")
        self.assertIsNotNone(tracker.get_habit("Read"))

    def test_a_bare_enter_is_treated_as_declining(self):
        tracker = self.seeded()
        self.drive(tracker, "11", "Read", "")
        self.assertEqual(len(tracker), 5)

    def test_an_unknown_habit_is_reported(self):
        self.assertIn("No habit named", self.drive(self.seeded(), "11", "Nothing"))


class DescribeTests(CliTestCase):
    """The one-line habit summary used throughout the listings."""

    def test_it_names_the_habit_and_its_periodicity(self):
        habit = build_seed_habits(FIXED_END_DATE)[0]
        line = interface.describe(habit, FIXED_END_DATE)
        self.assertIn("Morning Exercise", line)
        self.assertIn("daily", line)

    def test_it_reports_both_streak_figures(self):
        habit = build_seed_habits(FIXED_END_DATE)[2]
        line = interface.describe(habit, FIXED_END_DATE)
        self.assertIn("current streak 0", line)
        self.assertIn("best 11", line)

    def test_a_streak_of_one_is_singular(self):
        habit = build_seed_habits(FIXED_END_DATE)[4]
        self.assertIn("current streak 1 week,", interface.describe(habit, FIXED_END_DATE))


class SessionTests(CliTestCase):
    """A whole session behaves like consecutive sessions on the same file."""

    def test_work_done_in_one_session_is_there_in_the_next(self):
        first = self.empty()
        self.drive(first, "1", "Stretch", "10 minutes", "daily", "2", "Stretch")

        second = HabitTracker(storage=JsonStorage(self.data_file))
        self.assertEqual(len(second.require_habit("Stretch").completions), 1)

    def test_several_actions_run_in_one_session(self):
        tracker = self.empty()
        tracker.create_habit("Stretch", "10 minutes", "daily")
        tracker.check_off("Stretch", datetime(2026, 3, 3, 9, 0))
        output = self.drive(tracker, "3", "8", "7")
        self.assertIn("Stretch", output)
        self.assertIn("Tracking 1 habits", output)


class ReferenceDateTests(CliTestCase):
    """The display functions take a reference date instead of only reading the clock.

    The menu leaves it out, so a running app uses the real date. Passing it is
    what lets these tests assert on streaks without depending on the day they
    happen to run, and it is why the fixture date below can be pinned.
    """

    def capture(self, action) -> str:
        """Run one display action with no input needed and return its output."""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            action()
        return buffer.getvalue()

    def setUp(self):
        super().setUp()
        self.tracker = HabitTracker(
            storage=self.storage, habits=build_seed_habits(FIXED_END_DATE)
        )

    def test_statistics_honour_the_given_date(self):
        output = self.capture(lambda: interface.show_statistics(self.tracker, FIXED_END_DATE))
        row = next(line for line in output.splitlines() if "Morning Exercise" in line and "check-offs" in line)
        self.assertIn("(on 28)", row)

    def test_statistics_without_a_date_read_the_real_clock(self):
        # The fixture ends in the past, so every habit has since lapsed.
        output = self.capture(lambda: interface.show_statistics(self.tracker))
        rows = [line for line in output.splitlines() if "check-offs" in line]
        self.assertTrue(all("broken" in line for line in rows))

    def test_listings_honour_the_given_date(self):
        output = self.capture(lambda: interface.list_all(self.tracker, FIXED_END_DATE))
        self.assertIn("current streak 28 days", output)

    def test_the_struggle_window_honours_the_given_date(self):
        output = self.capture(lambda: interface.show_struggles(self.tracker, FIXED_END_DATE))
        self.assertIn("Meditate", output)
        self.assertIn("45%", output)

if __name__ == "__main__":
    unittest.main()
