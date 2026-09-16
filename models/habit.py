"""The `Habit` entity: a task, a period, and the log of times it was done."""

from datetime import date, datetime
from typing import Iterable, Optional

from models.completion import Completion
from models.periodicity import Periodicity


class Habit:
    """A task the user has committed to completing once per period.

    A habit owns its own event log and knows how to read it, so streak logic
    lives next to the data it interprets rather than in the analytics layer.
    Analytics stays free to be purely functional because everything it needs is
    already a query on the habit.

    Attributes:
        name: Unique, human-readable identifier.
        description: What the task actually involves.
        periodicity: How often the task must be checked off.
        created_at: When the habit was first defined.
        completions: Check-off events, oldest first.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        periodicity: "str | Periodicity" = Periodicity.DAILY,
        created_at: Optional[datetime] = None,
        completions: Optional[Iterable[Completion]] = None,
    ):
        """Define a habit.

        Args:
            name: Unique name; leading and trailing whitespace is stripped.
            description: What the task involves.
            periodicity: ``"daily"``, ``"weekly"``, or a `Periodicity`.
            created_at: Creation timestamp; defaults to now.
            completions: Existing check-offs, used when loading from storage.

        Raises:
            ValueError: if the name is blank or the periodicity is unsupported.
        """
        name = name.strip()
        if not name:
            raise ValueError("A habit needs a name")

        self.name = name
        self.description = description.strip()
        self.periodicity = Periodicity.parse(periodicity)
        self.created_at = created_at or datetime.now()
        self.completions: list[Completion] = sorted(
            completions or [], key=lambda c: (c.date, c.time)
        )

    def edit(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        periodicity: "str | Periodicity | None" = None,
    ) -> None:
        """Change a habit's definition in place, leaving the event log intact.

        Only the arguments actually supplied are applied, so callers can change
        one field without restating the others. Changing the periodicity
        re-interprets the existing completions under the new period, which is
        deliberate: the check-offs happened, only the yardstick changed.

        Raises:
            ValueError: if the new name is blank or the periodicity is unsupported.
        """
        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("A habit needs a name")
            self.name = name
        if description is not None:
            self.description = description.strip()
        if periodicity is not None:
            self.periodicity = Periodicity.parse(periodicity)

    def check_off(self, moment: Optional[datetime] = None) -> Completion:
        """Record that the task was completed.

        Args:
            moment: When it was completed; defaults to now. Passing it
                explicitly is what lets the fixtures build historical data.

        Returns:
            The `Completion` that was appended.
        """
        completion = Completion.at(moment) if moment else Completion.now()
        self.completions.append(completion)
        self.completions.sort(key=lambda c: (c.date, c.time))
        return completion

    def completion_dates(self) -> list[date]:
        """Every check-off date, oldest first, duplicates included."""
        return [c.as_date for c in self.completions]

    def is_completed_on(self, day: date) -> bool:
        """Whether the period containing `day` already has a check-off."""
        target = self.periodicity.period_index(day)
        return any(self.periodicity.period_index(c.as_date) == target for c in self.completions)

    def completed_periods(self) -> list[int]:
        """Sorted, de-duplicated indices of every period with a check-off.

        Two check-offs on the same day, or twice in one week for a weekly habit,
        collapse to a single period here — the brief only asks that a task be
        completed *at least* once per period.
        """
        return sorted({self.periodicity.period_index(c.as_date) for c in self.completions})

    def longest_streak(self) -> int:
        """Longest run of consecutive periods anywhere in the habit's history.

        Returns:
            The run length in periods; 0 if the habit was never checked off.
        """
        periods = self.completed_periods()
        if not periods:
            return 0

        longest = run = 1
        for previous, current in zip(periods, periods[1:]):
            run = run + 1 if current == previous + 1 else 1
            longest = max(longest, run)
        return longest

    def current_streak(self, today: Optional[date] = None) -> int:
        """Run of consecutive periods still unbroken as of `today`.

        The current period is not counted against the user until it ends: a
        daily habit checked off yesterday but not yet today still has its
        streak, because there is time left to do it. The streak is only broken
        once a whole period passes with no check-off.

        Args:
            today: Reference date; defaults to the current date. Tests and
                fixtures pass it explicitly to stay deterministic.

        Returns:
            The run length in periods; 0 if the habit is broken or unused.
        """
        periods = self.completed_periods()
        if not periods:
            return 0

        now = self.periodicity.period_index(today or date.today())
        if periods[-1] < now - 1:
            return 0

        streak = 1
        for previous, current in zip(reversed(periods[:-1]), reversed(periods)):
            if previous != current - 1:
                break
            streak += 1
        return streak

    def is_broken(self, today: Optional[date] = None) -> bool:
        """Whether a period has elapsed with the task left undone."""
        return self.current_streak(today) == 0

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dict."""
        return {
            "name": self.name,
            "description": self.description,
            "periodicity": self.periodicity.value,
            "created_at": self.created_at.isoformat(),
            "completions": [c.to_dict() for c in self.completions],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Habit":
        """Rebuild a habit from its serialised form.

        Accepts the `created_date` key written by the pre-Phase-3 flat version
        of the app so older data files still load.

        Raises:
            KeyError: if a required field is missing.
            ValueError: if a stored value cannot be parsed.
        """
        created = data.get("created_at") or data.get("created_date")
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            periodicity=data["periodicity"],
            created_at=datetime.fromisoformat(created) if created else None,
            completions=[Completion.from_dict(c) for c in data.get("completions", [])],
        )

    def __repr__(self) -> str:
        return f"Habit(name={self.name!r}, periodicity={self.periodicity.value!r}, completions={len(self.completions)})"
