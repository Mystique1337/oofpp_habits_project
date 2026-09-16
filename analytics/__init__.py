"""Functional analytics over a collection of habits.

Re-exported here so callers can write `from analytics import longest_streak_all`
without knowing which module it sits in.
"""

from analytics.metrics import (
    all_habit_names,
    completion_rate,
    completion_totals,
    current_streaks,
    habit_names_by_periodicity,
    habits_by_periodicity,
    longest_streak_all,
    longest_streak_for,
    struggled_most_since,
    summarise,
)

__all__ = [
    "all_habit_names",
    "completion_rate",
    "completion_totals",
    "current_streaks",
    "habit_names_by_periodicity",
    "habits_by_periodicity",
    "longest_streak_all",
    "longest_streak_for",
    "struggled_most_since",
    "summarise",
]
