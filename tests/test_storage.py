"""Tests for `JsonStorage`.

Covers the two things the rest of the app trusts it for: a habit written out
comes back the same, and a file that cannot be understood is reported rather
than quietly treated as "no habits yet".
"""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from models.habit import Habit
from storage.json_storage import JsonStorage, StorageError


def sample_habits() -> list[Habit]:
    """Two habits with a little history, one of each periodicity."""
    daily = Habit("Read", "20 pages", "daily", created_at=datetime(2026, 2, 1, 8, 0))
    daily.check_off(datetime(2026, 3, 3, 21, 0))
    daily.check_off(datetime(2026, 3, 4, 21, 0))

    weekly = Habit("Weekly Review", "plan the week", "weekly", created_at=datetime(2026, 2, 1, 8, 0))
    weekly.check_off(datetime(2026, 3, 1, 17, 0))
    return [daily, weekly]


class StorageTestCase(unittest.TestCase):
    """Base case giving each test a throwaway directory."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "habits.json"
        self.storage = JsonStorage(self.path)


class LoadTests(StorageTestCase):
    """Loading is forgiving about a missing file and strict about a broken one."""

    def test_a_missing_file_loads_as_no_habits(self):
        self.assertFalse(self.storage.exists())
        self.assertEqual(self.storage.load(), [])

    def test_invalid_json_is_reported(self):
        self.path.write_text("{not json at all", encoding="utf-8")
        with self.assertRaises(StorageError):
            self.storage.load()

    def test_json_without_a_habits_key_is_reported(self):
        self.path.write_text(json.dumps({"something_else": []}), encoding="utf-8")
        with self.assertRaises(StorageError):
            self.storage.load()

    def test_a_habit_missing_a_required_field_is_reported(self):
        self.path.write_text(json.dumps({"habits": [{"name": "Read"}]}), encoding="utf-8")
        with self.assertRaises(StorageError):
            self.storage.load()

    def test_a_habit_with_an_unparseable_date_is_reported(self):
        record = {
            "name": "Read",
            "periodicity": "daily",
            "created_at": "2026-02-01T08:00:00",
            "completions": [{"date": "not-a-date", "time": "21:00:00"}],
        }
        self.path.write_text(json.dumps({"habits": [record]}), encoding="utf-8")
        with self.assertRaises(StorageError):
            self.storage.load()


class SaveTests(StorageTestCase):
    """Saving creates the file, replaces its contents, and keeps it readable."""

    def test_saving_creates_the_file(self):
        self.storage.save(sample_habits())
        self.assertTrue(self.storage.exists())

    def test_an_empty_list_saves_and_loads(self):
        self.storage.save([])
        self.assertEqual(self.storage.load(), [])

    def test_the_file_is_human_readable_json(self):
        self.storage.save(sample_habits())
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual([h["name"] for h in payload["habits"]], ["Read", "Weekly Review"])

    def test_the_file_records_a_schema_version(self):
        self.storage.save(sample_habits())
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertIn("version", payload)

    def test_saving_replaces_rather_than_appends(self):
        self.storage.save(sample_habits())
        self.storage.save(sample_habits()[:1])
        self.assertEqual([h.name for h in self.storage.load()], ["Read"])

    def test_missing_parent_directories_are_created(self):
        nested = JsonStorage(Path(self.directory.name) / "deep" / "nested" / "habits.json")
        nested.save(sample_habits())
        self.assertTrue(nested.exists())

    def test_no_temporary_files_are_left_behind(self):
        self.storage.save(sample_habits())
        self.assertEqual([p.name for p in Path(self.directory.name).iterdir()], ["habits.json"])


class RoundTripTests(StorageTestCase):
    """What comes back out is what went in."""

    def setUp(self):
        super().setUp()
        self.original = sample_habits()
        self.storage.save(self.original)
        self.restored = self.storage.load()

    def test_every_habit_comes_back(self):
        self.assertEqual(
            [h.name for h in self.restored], [h.name for h in self.original]
        )

    def test_definitions_survive(self):
        for before, after in zip(self.original, self.restored):
            self.assertEqual(after.description, before.description)
            self.assertIs(after.periodicity, before.periodicity)
            self.assertEqual(after.created_at, before.created_at)

    def test_event_logs_survive(self):
        for before, after in zip(self.original, self.restored):
            self.assertEqual(after.completions, before.completions)

    def test_streaks_are_unchanged_by_the_round_trip(self):
        for before, after in zip(self.original, self.restored):
            self.assertEqual(after.longest_streak(), before.longest_streak())


if __name__ == "__main__":
    unittest.main()
