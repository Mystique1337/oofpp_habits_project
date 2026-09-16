"""`HabitTracker`: the collection of habits and the one thing that saves them."""

from datetime import datetime
from typing import Iterable, Optional

from models.habit import Habit
from models.periodicity import Periodicity
from storage.json_storage import JsonStorage


class DuplicateHabitError(ValueError):
    """Raised when a habit name is already taken."""


class HabitNotFoundError(KeyError):
    """Raised when no habit matches the given name."""

    def __str__(self) -> str:
        return str(self.args[0]) if self.args else ""


class HabitTracker:
    """Owns the set of tracked habits and keeps the store in step with it.

    Every method that changes the collection writes through to storage, so the
    CLI never has to remember to save. Storage is injected rather than opened
    here, which is what lets the tests run against a temporary file and what
    would let a SQLite backend drop in unchanged.
    """

    def __init__(self, storage: Optional[JsonStorage] = None, habits: Optional[Iterable[Habit]] = None):
        """Create a tracker.

        Args:
            storage: Where habits are persisted. Defaults to `JsonStorage` on
                its own default path.
            habits: Starting habits. When given, storage is *not* read, which
                is how the seed data and the tests build a known state.
        """
        self.storage = storage or JsonStorage()
        self.habits: list[Habit] = list(habits) if habits is not None else self.storage.load()

    def create_habit(
        self,
        name: str,
        description: str = "",
        periodicity: "str | Periodicity" = Periodicity.DAILY,
    ) -> Habit:
        """Define and persist a new habit.

        Raises:
            DuplicateHabitError: if the name is already in use.
            ValueError: if the name is blank or the periodicity is unsupported.
        """
        habit = Habit(name, description, periodicity)
        if self.get_habit(habit.name):
            raise DuplicateHabitError(f"A habit named {habit.name!r} already exists")

        self.habits.append(habit)
        self.save()
        return habit

    def edit_habit(
        self,
        name: str,
        new_name: Optional[str] = None,
        description: Optional[str] = None,
        periodicity: "str | Periodicity | None" = None,
    ) -> Habit:
        """Change a habit's definition, keeping its completion history.

        Raises:
            HabitNotFoundError: if no habit has that name.
            DuplicateHabitError: if `new_name` is already taken by another habit.
            ValueError: if the new name is blank or the periodicity is unsupported.
        """
        habit = self.require_habit(name)
        if new_name and new_name.strip() != habit.name:
            clash = self.get_habit(new_name)
            if clash:
                raise DuplicateHabitError(f"A habit named {clash.name!r} already exists")

        habit.edit(name=new_name, description=description, periodicity=periodicity)
        self.save()
        return habit

    def delete_habit(self, name: str) -> Habit:
        """Remove a habit and its history.

        Returns:
            The habit that was removed.

        Raises:
            HabitNotFoundError: if no habit has that name.
        """
        habit = self.require_habit(name)
        self.habits.remove(habit)
        self.save()
        return habit

    def check_off(self, name: str, moment: Optional[datetime] = None) -> Habit:
        """Record a completion for a habit and persist it.

        Raises:
            HabitNotFoundError: if no habit has that name.
        """
        habit = self.require_habit(name)
        habit.check_off(moment)
        self.save()
        return habit

    def get_habit(self, name: str) -> Optional[Habit]:
        """Find a habit by name, case-insensitively. `None` if there is no match."""
        wanted = name.strip().casefold()
        return next((h for h in self.habits if h.name.casefold() == wanted), None)

    def require_habit(self, name: str) -> Habit:
        """Find a habit by name.

        Raises:
            HabitNotFoundError: if no habit has that name.
        """
        habit = self.get_habit(name)
        if habit is None:
            raise HabitNotFoundError(f"No habit named {name.strip()!r}")
        return habit

    def save(self) -> None:
        """Write the current habits to storage."""
        self.storage.save(self.habits)

    def reload(self) -> None:
        """Discard in-memory state and re-read storage."""
        self.habits = self.storage.load()

    def __len__(self) -> int:
        return len(self.habits)

    def __iter__(self):
        return iter(self.habits)
