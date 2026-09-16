"""The five predefined habits and four weeks of check-offs for each.

The data serves two jobs, which is why it is generated rather than written out
as a literal JSON file:

* As a demo, `build_seed_habits()` ends the four weeks on today, so a fresh
  install opens on habits with live-looking streaks.
* As a test fixture, the tests pass a fixed `end_date`, which makes every
  expected streak below a constant rather than something that drifts with the
  calendar.

The patterns are hand-designed so each one exercises a different branch of the
streak logic: an unbroken run, a run with gaps, a habit that has lapsed, a
perfect weekly run, and a weekly habit with both a skipped week and two
check-offs inside one week.

Daily check-offs are expressed as "days before the end date". Weekly ones are
anchored to the Monday of the end date's week so the patterns hold whatever
weekday the app happens to be run on.
"""

from datetime import date, datetime, time, timedelta
from typing import NamedTuple, Optional

from models.habit import Habit
from models.periodicity import Periodicity
from models.tracker import HabitTracker

WEEKS_OF_DATA = 4
DAYS_OF_DATA = WEEKS_OF_DATA * 7


class SeedSpec(NamedTuple):
    """The definition of one predefined habit and the pattern of its check-offs.

    Attributes:
        name: Habit name.
        description: What the task involves.
        periodicity: How often it must be done.
        check_off_time: Time of day stamped on every generated completion.
        offsets: For daily habits, days before the end date. For weekly habits,
            ``(weeks_before, weekday)`` pairs, where weekday is 0 for Monday.
        story: Why this pattern is in the fixture.
    """

    name: str
    description: str
    periodicity: Periodicity
    check_off_time: time
    offsets: tuple
    story: str


SEED_SPECS: tuple[SeedSpec, ...] = (
    SeedSpec(
        name="Morning Exercise",
        description="30 minutes of exercise before starting work",
        periodicity=Periodicity.DAILY,
        check_off_time=time(6, 45),
        offsets=tuple(range(DAYS_OF_DATA)),
        story="Never missed: the whole 28 days is one streak.",
    ),
    SeedSpec(
        name="Read",
        description="Read at least 20 pages of a book",
        periodicity=Periodicity.DAILY,
        check_off_time=time(21, 30),
        offsets=tuple(day for day in range(DAYS_OF_DATA) if day not in {3, 12, 20}),
        story="Three scattered misses, so the longest run sits mid-history.",
    ),
    SeedSpec(
        name="Meditate",
        description="10 minutes of guided meditation",
        periodicity=Periodicity.DAILY,
        check_off_time=time(7, 15),
        offsets=tuple(range(17, DAYS_OF_DATA)) + (8, 7, 6),
        story="Started strong, then lapsed: the current streak is broken.",
    ),
    SeedSpec(
        name="Weekly Review",
        description="Review the week's goals and plan the next one",
        periodicity=Periodicity.WEEKLY,
        check_off_time=time(17, 0),
        offsets=((3, 6), (2, 6), (1, 6), (0, 6)),
        story="One check-off in each of the four weeks.",
    ),
    SeedSpec(
        name="Team Meeting",
        description="Attend the weekly team check-in",
        periodicity=Periodicity.WEEKLY,
        check_off_time=time(10, 0),
        offsets=((3, 2), (3, 4), (2, 2), (0, 2)),
        story="A skipped week, plus two check-offs inside one week to prove "
        "repeats within a period do not inflate the streak.",
    ),
)

EXPECTED_LONGEST_STREAKS = {
    "Morning Exercise": 28,
    "Read": 8,
    "Meditate": 11,
    "Weekly Review": 4,
    "Team Meeting": 2,
}
"""Longest streak each seeded habit should report, for the tests to assert on.

These are properties of the patterns above and do not depend on the end date.
"""

EXPECTED_CURRENT_STREAKS = {
    "Morning Exercise": 28,
    "Read": 3,
    "Meditate": 0,
    "Weekly Review": 4,
    "Team Meeting": 1,
}
"""Current streak each seeded habit should report on the fixture's end date."""


def _daily_moments(spec: SeedSpec, end_date: date) -> list[datetime]:
    """Turn day offsets into timestamps counting back from `end_date`."""
    return [
        datetime.combine(end_date - timedelta(days=offset), spec.check_off_time)
        for offset in spec.offsets
    ]


def _weekly_moments(spec: SeedSpec, end_date: date) -> list[datetime]:
    """Turn (weeks_before, weekday) pairs into timestamps.

    Anchoring on the Monday of `end_date`'s week keeps each check-off inside the
    week it is meant to be in no matter which weekday the app is run on. A day
    in the current week that would fall after `end_date` is pulled back to it,
    so the fixture never records a check-off in the future.
    """
    this_monday = end_date - timedelta(days=end_date.weekday())
    moments = []
    for weeks_before, weekday in spec.offsets:
        day = this_monday - timedelta(weeks=weeks_before) + timedelta(days=weekday)
        moments.append(datetime.combine(min(day, end_date), spec.check_off_time))
    return moments


def build_seed_habits(end_date: Optional[date] = None) -> list[Habit]:
    """Build the five predefined habits with four weeks of check-offs each.

    Args:
        end_date: Last day covered by the data; defaults to today. Tests pass a
            fixed date so the expected streaks stay constant.

    Returns:
        Five habits — three daily, two weekly — each with its completions
        already recorded.
    """
    end_date = end_date or date.today()
    created_at = datetime.combine(end_date - timedelta(days=DAYS_OF_DATA - 1), time(8, 0))

    habits = []
    for spec in SEED_SPECS:
        habit = Habit(spec.name, spec.description, spec.periodicity, created_at=created_at)
        moments = (
            _daily_moments(spec, end_date)
            if spec.periodicity is Periodicity.DAILY
            else _weekly_moments(spec, end_date)
        )
        for moment in moments:
            habit.check_off(moment)
        habits.append(habit)
    return habits


def seeded_tracker(storage=None, end_date: Optional[date] = None) -> HabitTracker:
    """A tracker preloaded with the predefined habits.

    Args:
        storage: Where to persist. Defaults to the standard data file.
        end_date: Last day covered by the seeded data; defaults to today.

    Returns:
        A saved tracker holding the five predefined habits.
    """
    tracker = HabitTracker(storage=storage, habits=build_seed_habits(end_date))
    tracker.save()
    return tracker
