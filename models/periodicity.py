"""How often a habit must be checked off.

The whole streak calculation rests on one idea in this module: every date maps
to an integer index for the period it falls in, and two periods are consecutive
exactly when their indices differ by one. That keeps `Habit` free of
`if daily ... elif weekly ...` branches and means a third periodicity only has
to answer `period_index` to work everywhere.
"""

from datetime import date, timedelta
from enum import Enum


class Periodicity(str, Enum):
    """The tracking periods the application supports."""

    DAILY = "daily"
    WEEKLY = "weekly"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def parse(cls, value: "str | Periodicity") -> "Periodicity":
        """Read a periodicity from user input or from stored JSON.

        Args:
            value: A `Periodicity`, or a string such as ``"Daily"``.

        Returns:
            The matching `Periodicity`.

        Raises:
            ValueError: if the value names no supported periodicity.
        """
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            supported = ", ".join(p.value for p in cls)
            raise ValueError(f"Unknown periodicity {value!r}; expected one of: {supported}") from None

    def period_index(self, day: date) -> int:
        """Index of the period `day` falls in.

        Consecutive periods differ by exactly one, which is what makes a streak
        a run of consecutive integers.

        For `WEEKLY` the index is derived from the Monday that starts the week,
        so Sunday and the following Monday land in different weeks, matching ISO
        week numbering.
        """
        if self is Periodicity.DAILY:
            return day.toordinal()
        monday = day - timedelta(days=day.weekday())
        return monday.toordinal() // 7

    @property
    def unit(self) -> str:
        """Singular noun for one period, for use in messages."""
        return "day" if self is Periodicity.DAILY else "week"
