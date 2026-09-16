"""Analytics, written in the functional paradigm.

Every function here is pure: it takes habits in, returns a new value out, and
mutates nothing — no habit is modified, no file is touched, no module-level
state is kept. That is what the brief asks for, and it has a practical payoff:
each function can be tested by handing it a list and comparing the result, with
no fixtures to tear down.

The implementations lean on `map`, `filter`, `reduce`, comprehensions and
`lambda` rather than accumulator loops. Where a comprehension reads better than
`map` over a `lambda`, the comprehension wins — it is still a pure expression
over the input, which is the part that matters.

All functions accept any iterable of `Habit`, so a `HabitTracker` (which is
iterable) can be passed directly.
"""

from datetime import date
from functools import reduce
from typing import Callable, Iterable, Optional

from models.habit import Habit
from models.periodicity import Periodicity

Habits = Iterable[Habit]


def all_habit_names(habits: Habits) -> list[str]:
    """Names of every currently tracked habit.

    Args:
        habits: The habits to list.

    Returns:
        The habit names, in the order the habits are held.
    """
    return list(map(lambda habit: habit.name, habits))


def habits_by_periodicity(habits: Habits, periodicity: "str | Periodicity") -> list[Habit]:
    """Habits sharing one periodicity.

    Args:
        habits: The habits to filter.
        periodicity: ``"daily"``, ``"weekly"``, or a `Periodicity`.

    Returns:
        The matching habits.

    Raises:
        ValueError: if the periodicity is unsupported.
    """
    wanted = Periodicity.parse(periodicity)
    return list(filter(lambda habit: habit.periodicity is wanted, habits))


def habit_names_by_periodicity(habits: Habits, periodicity: "str | Periodicity") -> list[str]:
    """Names of the habits sharing one periodicity.

    Raises:
        ValueError: if the periodicity is unsupported.
    """
    return all_habit_names(habits_by_periodicity(habits, periodicity))


def longest_streak_all(habits: Habits) -> tuple[Optional[str], int]:
    """The best run streak achieved across every habit.

    Ties are broken by the order the habits are held, so the first habit to
    reach the top streak is the one reported.

    Args:
        habits: The habits to compare.

    Returns:
        ``(habit_name, streak_length)``, or ``(None, 0)`` when there are no
        habits to compare.
    """
    scores = list(map(lambda habit: (habit.name, habit.longest_streak()), habits))
    if not scores:
        return None, 0
    return reduce(lambda best, current: current if current[1] > best[1] else best, scores)


def longest_streak_for(habits: Habits, name: str) -> int:
    """The best run streak for one habit.

    Args:
        habits: The habits to search.
        name: Habit name, matched case-insensitively.

    Returns:
        The streak length in periods.

    Raises:
        KeyError: if no habit has that name. Returning 0 would be
            indistinguishable from a real habit that was never checked off.
    """
    wanted = name.strip().casefold()
    match = next(filter(lambda habit: habit.name.casefold() == wanted, habits), None)
    if match is None:
        raise KeyError(f"No habit named {name.strip()!r}")
    return match.longest_streak()


def current_streaks(habits: Habits, today: Optional[date] = None) -> dict[str, int]:
    """Each habit's streak as it stands right now.

    Args:
        habits: The habits to measure.
        today: Reference date; defaults to the current date.

    Returns:
        Habit name to unbroken run length in periods.
    """
    return {habit.name: habit.current_streak(today) for habit in habits}


def completion_totals(habits: Habits) -> dict[str, int]:
    """Total check-offs recorded per habit, duplicates within a period included."""
    return {habit.name: len(habit.completions) for habit in habits}


def completion_rate(habit: Habit, since: date, until: Optional[date] = None) -> float:
    """Share of the periods in a window that the habit was completed in.

    Args:
        habit: The habit to measure.
        since: First date of the window, inclusive.
        until: Last date of the window, inclusive; defaults to today.

    Returns:
        A value from 0.0 to 1.0. An empty or inverted window returns 0.0.
    """
    until = until or date.today()
    if until < since:
        return 0.0

    index = habit.periodicity.period_index
    window = range(index(since), index(until) + 1)
    if not len(window):
        return 0.0

    hit = set(habit.completed_periods())
    return len(list(filter(lambda period: period in hit, window))) / len(window)


def struggled_most_since(
    habits: Habits, since: date, until: Optional[date] = None, limit: int = 3
) -> list[tuple[str, float]]:
    """The habits with the worst completion rate over a window.

    This answers the brief's question "with which habits did I struggle most
    last month?" — pass ``since=date.today() - timedelta(days=30)``.

    Args:
        habits: The habits to rank.
        since: First date of the window, inclusive.
        until: Last date of the window, inclusive; defaults to today.
        limit: How many habits to return.

    Returns:
        Up to `limit` ``(habit_name, completion_rate)`` pairs, worst first.
        Habits created after the window ends are left out, since there was
        nothing to miss.
    """
    until = until or date.today()
    in_scope: Callable[[Habit], bool] = lambda habit: habit.created_at.date() <= until
    scored = map(
        lambda habit: (habit.name, completion_rate(habit, since, until)),
        filter(in_scope, habits),
    )
    return sorted(scored, key=lambda scored_habit: (scored_habit[1], scored_habit[0]))[:limit]


def summarise(habits: Habits, today: Optional[date] = None) -> dict:
    """One report covering every metric the CLI's statistics screen shows.

    Args:
        habits: The habits to summarise.
        today: Reference date; defaults to the current date.

    Returns:
        Totals per periodicity, the best streak overall, and a per-habit
        breakdown of periodicity, check-off count, current and longest streak.
    """
    habits = list(habits)
    today = today or date.today()
    best_name, best_streak = longest_streak_all(habits)

    return {
        "total_habits": len(habits),
        "daily_habits": len(habits_by_periodicity(habits, Periodicity.DAILY)),
        "weekly_habits": len(habits_by_periodicity(habits, Periodicity.WEEKLY)),
        "best_habit": best_name,
        "best_streak": best_streak,
        "habits": list(
            map(
                lambda habit: {
                    "name": habit.name,
                    "periodicity": habit.periodicity.value,
                    "created_at": habit.created_at.date().isoformat(),
                    "completions": len(habit.completions),
                    "current_streak": habit.current_streak(today),
                    "longest_streak": habit.longest_streak(),
                    "broken": habit.is_broken(today),
                },
                habits,
            )
        ),
    }
