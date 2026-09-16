"""Tests for `HabitTracker`: creation, editing, deletion and write-through.

Each test gets its own tracker backed by a temporary file, so nothing here can
touch the data file a user is actually keeping habits in.
"""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from models.habit import Habit
from models.tracker import DuplicateHabitError, HabitNotFoundError, HabitTracker
from storage.json_storage import JsonStorage


class TrackerTestCase(unittest.TestCase):
    """Base case giving each test an empty tracker on a throwaway file."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.data_file = Path(self.directory.name) / "habits.json"
        self.storage = JsonStorage(self.data_file)
        self.tracker = HabitTracker(storage=self.storage, habits=[])

    def reopen(self) -> HabitTracker:
        """A second tracker reading the same file, to prove what was persisted."""
        return HabitTracker(storage=JsonStorage(self.data_file))


class CreateHabitTests(TrackerTestCase):
    """Creating a habit registers it and writes it out."""

    def test_a_created_habit_is_tracked(self):
        self.tracker.create_habit("Read", "20 pages", "daily")
        self.assertEqual(len(self.tracker), 1)

    def test_a_created_habit_is_persisted_immediately(self):
        self.tracker.create_habit("Read", "20 pages", "daily")
        self.assertEqual([h.name for h in self.reopen()], ["Read"])

    def test_create_returns_the_new_habit(self):
        habit = self.tracker.create_habit("Read", "20 pages", "weekly")
        self.assertIsInstance(habit, Habit)
        self.assertEqual(habit.name, "Read")

    def test_a_duplicate_name_is_refused(self):
        self.tracker.create_habit("Read", "20 pages", "daily")
        with self.assertRaises(DuplicateHabitError):
            self.tracker.create_habit("Read", "something else", "weekly")

    def test_a_duplicate_name_is_refused_regardless_of_case(self):
        self.tracker.create_habit("Read", "20 pages", "daily")
        with self.assertRaises(DuplicateHabitError):
            self.tracker.create_habit("  read  ", "20 pages", "daily")

    def test_a_refused_duplicate_does_not_get_added(self):
        self.tracker.create_habit("Read", "20 pages", "daily")
        with self.assertRaises(DuplicateHabitError):
            self.tracker.create_habit("Read", "again", "daily")
        self.assertEqual(len(self.tracker), 1)

    def test_an_invalid_periodicity_is_refused(self):
        with self.assertRaises(ValueError):
            self.tracker.create_habit("Read", "20 pages", "monthly")
        self.assertEqual(len(self.tracker), 0)


class FindHabitTests(TrackerTestCase):
    """Lookups are case-insensitive and fail loudly when asked to."""

    def setUp(self):
        super().setUp()
        self.tracker.create_habit("Morning Exercise", "30 minutes", "daily")

    def test_get_habit_finds_it_regardless_of_case(self):
        self.assertIsNotNone(self.tracker.get_habit("morning exercise"))

    def test_get_habit_returns_none_when_absent(self):
        self.assertIsNone(self.tracker.get_habit("Nothing"))

    def test_require_habit_raises_when_absent(self):
        with self.assertRaises(HabitNotFoundError):
            self.tracker.require_habit("Nothing")


class EditHabitTests(TrackerTestCase):
    """Editing updates the definition, keeps the history and saves."""

    def setUp(self):
        super().setUp()
        self.tracker.create_habit("Read", "20 pages", "daily")
        self.tracker.check_off("Read", datetime(2026, 3, 4, 21, 0))

    def test_the_name_can_be_changed(self):
        self.tracker.edit_habit("Read", new_name="Read More")
        self.assertIsNotNone(self.tracker.get_habit("Read More"))
        self.assertIsNone(self.tracker.get_habit("Read"))

    def test_the_description_can_be_changed(self):
        self.tracker.edit_habit("Read", description="30 pages")
        self.assertEqual(self.tracker.require_habit("Read").description, "30 pages")

    def test_the_periodicity_can_be_changed(self):
        self.tracker.edit_habit("Read", periodicity="weekly")
        self.assertEqual(str(self.tracker.require_habit("Read").periodicity), "weekly")

    def test_editing_keeps_the_check_off_history(self):
        self.tracker.edit_habit("Read", new_name="Read More", periodicity="weekly")
        self.assertEqual(len(self.tracker.require_habit("Read More").completions), 1)

    def test_an_edit_is_persisted(self):
        self.tracker.edit_habit("Read", new_name="Read More")
        self.assertEqual([h.name for h in self.reopen()], ["Read More"])

    def test_renaming_onto_another_habit_is_refused(self):
        self.tracker.create_habit("Meditate", "10 minutes", "daily")
        with self.assertRaises(DuplicateHabitError):
            self.tracker.edit_habit("Read", new_name="Meditate")

    def test_editing_an_unknown_habit_is_reported(self):
        with self.assertRaises(HabitNotFoundError):
            self.tracker.edit_habit("Nothing", description="x")


class DeleteHabitTests(TrackerTestCase):
    """Deleting removes the habit and its history, and saves."""

    def setUp(self):
        super().setUp()
        self.tracker.create_habit("Read", "20 pages", "daily")
        self.tracker.create_habit("Meditate", "10 minutes", "daily")

    def test_the_habit_is_removed(self):
        self.tracker.delete_habit("Read")
        self.assertEqual([h.name for h in self.tracker], ["Meditate"])

    def test_delete_returns_the_removed_habit(self):
        self.assertEqual(self.tracker.delete_habit("Read").name, "Read")

    def test_the_deletion_is_persisted(self):
        self.tracker.delete_habit("Read")
        self.assertEqual([h.name for h in self.reopen()], ["Meditate"])

    def test_deleting_is_case_insensitive(self):
        self.tracker.delete_habit("  read ")
        self.assertEqual(len(self.tracker), 1)

    def test_deleting_an_unknown_habit_is_reported(self):
        with self.assertRaises(HabitNotFoundError):
            self.tracker.delete_habit("Nothing")

    def test_a_failed_delete_changes_nothing(self):
        with self.assertRaises(HabitNotFoundError):
            self.tracker.delete_habit("Nothing")
        self.assertEqual(len(self.tracker), 2)


class CheckOffTests(TrackerTestCase):
    """Check-offs go through the tracker so they are always saved."""

    def setUp(self):
        super().setUp()
        self.tracker.create_habit("Read", "20 pages", "daily")

    def test_a_check_off_is_recorded(self):
        self.tracker.check_off("Read", datetime(2026, 3, 4, 21, 0))
        self.assertEqual(len(self.tracker.require_habit("Read").completions), 1)

    def test_a_check_off_is_persisted(self):
        self.tracker.check_off("Read", datetime(2026, 3, 4, 21, 0))
        self.assertEqual(len(self.reopen().require_habit("Read").completions), 1)

    def test_checking_off_an_unknown_habit_is_reported(self):
        with self.assertRaises(HabitNotFoundError):
            self.tracker.check_off("Nothing")


class PersistenceTests(TrackerTestCase):
    """The tracker and the file stay in step across sessions."""

    def test_a_tracker_with_no_file_starts_empty(self):
        self.assertEqual(len(HabitTracker(storage=JsonStorage(self.data_file), habits=None)), 0)

    def test_a_full_session_round_trips(self):
        self.tracker.create_habit("Read", "20 pages", "daily")
        self.tracker.create_habit("Weekly Review", "plan the week", "weekly")
        self.tracker.check_off("Read", datetime(2026, 3, 3, 21, 0))
        self.tracker.check_off("Read", datetime(2026, 3, 4, 21, 0))

        restored = self.reopen()
        self.assertEqual(len(restored), 2)
        self.assertEqual(restored.require_habit("Read").longest_streak(), 2)

    def test_reload_discards_unsaved_in_memory_changes(self):
        self.tracker.create_habit("Read", "20 pages", "daily")
        self.tracker.habits.append(Habit("Ghost", "never saved", "daily"))
        self.tracker.reload()
        self.assertEqual([h.name for h in self.tracker], ["Read"])

    def test_the_tracker_is_iterable_and_sized(self):
        self.tracker.create_habit("Read", "20 pages", "daily")
        self.assertEqual(len(self.tracker), 1)
        self.assertEqual([h.name for h in self.tracker], ["Read"])


if __name__ == "__main__":
    unittest.main()
