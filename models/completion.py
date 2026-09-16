"""A single check-off event.

Completions are the event log of the application: a habit is never edited to
record progress, a new `Completion` is appended instead. Keeping them as their
own type (rather than bare dicts) gives the date arithmetic in `Habit` one place
to trust for parsing.
"""

from dataclasses import dataclass
from datetime import date, datetime, time


@dataclass(frozen=True)
class Completion:
    """One check-off of a habit, stored as ISO 8601 strings.

    Strings rather than `date`/`time` objects because the JSON file is meant to
    be readable and hand-editable; the typed values are exposed through the
    `as_date` and `as_time` properties.

    Attributes:
        date: ISO date the task was completed, e.g. ``"2026-01-02"``.
        time: ISO time the task was completed, e.g. ``"07:15:00"``.
    """

    date: str
    time: str

    def __post_init__(self) -> None:
        """Reject malformed timestamps at construction, including on load.

        Raises:
            ValueError: if either field is not a valid ISO 8601 string.
        """
        date.fromisoformat(self.date)
        time.fromisoformat(self.time)

    @classmethod
    def at(cls, moment: datetime) -> "Completion":
        """Build a completion from a `datetime`."""
        return cls(
            date=moment.date().isoformat(),
            time=moment.time().isoformat(timespec="seconds"),
        )

    @classmethod
    def now(cls) -> "Completion":
        """Build a completion stamped with the current local time."""
        return cls.at(datetime.now())

    @property
    def as_date(self) -> date:
        """The completion date as a `datetime.date`."""
        return date.fromisoformat(self.date)

    @property
    def as_time(self) -> time:
        """The completion time as a `datetime.time`."""
        return time.fromisoformat(self.time)

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dict."""
        return {"date": self.date, "time": self.time}

    @classmethod
    def from_dict(cls, data: dict) -> "Completion":
        """Rebuild a completion from its serialised form.

        Raises:
            KeyError: if `date` or `time` is missing.
            ValueError: if either value is not a valid ISO 8601 string.
        """
        return cls(date=data["date"], time=data["time"])
