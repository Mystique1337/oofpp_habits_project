"""The interactive menu loop.

Keeping prompting, formatting and dispatch here means the domain never has to
know it is being driven by a terminal. Each action is a small function taking
the tracker, so the menu is a plain table of label-to-function and adding a
screen is one entry plus one function.
"""

from datetime import date, timedelta
from typing import Callable, Optional

import analytics
from models.habit import Habit
from models.periodicity import Periodicity
from models.tracker import DuplicateHabitError, HabitNotFoundError, HabitTracker
from storage.json_storage import StorageError

RULE = "=" * 58
STRUGGLE_WINDOW_DAYS = 30


def ask(prompt: str) -> str:
    """Read one trimmed line from the user."""
    return input(prompt).strip()


def ask_required(prompt: str) -> Optional[str]:
    """Read a non-empty line, re-prompting until one is given.

    Returns:
        The entered text, or `None` if the user submits a blank line twice,
        which is taken as backing out of the action.
    """
    for _ in range(2):
        answer = ask(prompt)
        if answer:
            return answer
        print("A value is required. Press Enter again to cancel.")
    return None


def ask_periodicity() -> Optional[Periodicity]:
    """Read a periodicity, re-prompting until it is one we support."""
    options = "/".join(p.value for p in Periodicity)
    while True:
        answer = ask(f"Periodicity ({options}, blank to cancel): ")
        if not answer:
            return None
        try:
            return Periodicity.parse(answer)
        except ValueError as error:
            print(error)


def describe(habit: Habit, today: Optional[date] = None) -> str:
    """One-line summary of a habit for list output."""
    unit = habit.periodicity.unit
    current = habit.current_streak(today)
    plural = "" if current == 1 else "s"
    return (
        f"{habit.name} ({habit.periodicity}) - "
        f"{len(habit.completions)} check-offs, "
        f"current streak {current} {unit}{plural}, "
        f"best {habit.longest_streak()}"
    )


def show_habits(habits: list, empty_message: str, today: Optional[date] = None) -> None:
    """Print a numbered list of habits, or a message if there are none."""
    if not habits:
        print(empty_message)
        return
    for position, habit in enumerate(habits, start=1):
        print(f"{position}. {describe(habit, today)}")
        if habit.description:
            print(f"   {habit.description}")


def create_habit(tracker: HabitTracker) -> None:
    """Prompt for a new habit and add it."""
    print("\n-- New habit --")
    name = ask_required("Name: ")
    if name is None:
        return
    description = ask("Description (optional): ")
    periodicity = ask_periodicity()
    if periodicity is None:
        return

    try:
        habit = tracker.create_habit(name, description, periodicity)
    except (DuplicateHabitError, ValueError) as error:
        print(error)
        return
    print(f"Created {habit.name}, to be completed every {habit.periodicity.unit}.")


def edit_habit(tracker: HabitTracker, today: Optional[date] = None) -> None:
    """Prompt for changes to an existing habit, keeping its check-off history."""
    print("\n-- Edit habit --")
    show_habits(tracker.habits, "No habits to edit yet.", today)
    if not tracker.habits:
        return

    name = ask_required("Habit to edit: ")
    if name is None:
        return
    try:
        habit = tracker.require_habit(name)
    except HabitNotFoundError as error:
        print(error)
        return

    print("Leave a field blank to keep it as it is.")
    new_name = ask(f"Name [{habit.name}]: ")
    description = ask(f"Description [{habit.description}]: ")
    periodicity = ask(f"Periodicity [{habit.periodicity}]: ")

    try:
        tracker.edit_habit(
            habit.name,
            new_name=new_name or None,
            description=description or None,
            periodicity=periodicity or None,
        )
    except (DuplicateHabitError, ValueError) as error:
        print(error)
        return
    print(f"Updated: {describe(habit, today)}")


def delete_habit(tracker: HabitTracker, today: Optional[date] = None) -> None:
    """Prompt for a habit to remove, confirming first."""
    print("\n-- Delete habit --")
    show_habits(tracker.habits, "No habits to delete.", today)
    if not tracker.habits:
        return

    name = ask_required("Habit to delete: ")
    if name is None:
        return
    try:
        habit = tracker.require_habit(name)
    except HabitNotFoundError as error:
        print(error)
        return

    confirm = ask(f"Delete {habit.name} and its {len(habit.completions)} check-offs? (y/N): ")
    if confirm.lower() not in {"y", "yes"}:
        print("Left alone.")
        return
    tracker.delete_habit(habit.name)
    print(f"Deleted {habit.name}.")


def check_off(tracker: HabitTracker, today: Optional[date] = None) -> None:
    """Record a completion for a habit."""
    print("\n-- Check off a task --")
    show_habits(tracker.habits, "No habits yet. Create one first.", today)
    if not tracker.habits:
        return

    name = ask_required("Habit completed: ")
    if name is None:
        return
    try:
        habit = tracker.require_habit(name)
    except HabitNotFoundError as error:
        print(error)
        return

    already_done = habit.is_completed_on(today or date.today())
    tracker.check_off(habit.name)
    if already_done:
        print(
            f"Recorded. {habit.name} was already done this "
            f"{habit.periodicity.unit}, so the streak is unchanged."
        )
    print(describe(habit, today))


def list_all(tracker: HabitTracker, today: Optional[date] = None) -> None:
    """Show every tracked habit."""
    print("\n-- All habits --")
    show_habits(tracker.habits, "No habits yet.", today)


def list_by_periodicity(
    tracker: HabitTracker, periodicity: Periodicity, today: Optional[date] = None
) -> None:
    """Show habits with one periodicity."""
    print(f"\n-- {periodicity.value.capitalize()} habits --")
    matches = analytics.habits_by_periodicity(tracker, periodicity)
    show_habits(matches, f"No {periodicity} habits yet.", today)


def show_streak_for_habit(tracker: HabitTracker, today: Optional[date] = None) -> None:
    """Show both streak figures for one habit."""
    print("\n-- Streak for one habit --")
    name = ask_required("Habit name: ")
    if name is None:
        return
    try:
        habit = tracker.require_habit(name)
    except HabitNotFoundError as error:
        print(error)
        return

    unit = habit.periodicity.unit
    print(
        f"{habit.name}: longest run {habit.longest_streak()} {unit}s, "
        f"current run {habit.current_streak(today)} {unit}s"
    )


def show_best_streak(tracker: HabitTracker) -> None:
    """Show the best streak achieved across all habits."""
    print("\n-- Longest streak, all habits --")
    name, streak = analytics.longest_streak_all(tracker)
    if name is None:
        print("No habits yet.")
        return
    unit = tracker.require_habit(name).periodicity.unit
    print(f"{name} holds the record at {streak} consecutive {unit}s.")


def show_statistics(tracker: HabitTracker, today: Optional[date] = None) -> None:
    """Show the full analytics summary."""
    print("\n-- Statistics --")
    report = analytics.summarise(tracker, today)
    print(
        f"Tracking {report['total_habits']} habits "
        f"({report['daily_habits']} daily, {report['weekly_habits']} weekly)"
    )
    if report["best_habit"]:
        print(f"Best streak: {report['best_habit']} at {report['best_streak']} periods")

    for row in report["habits"]:
        state = "broken" if row["broken"] else f"on {row['current_streak']}"
        print(
            f"  {row['name']:<20} {row['periodicity']:<8} "
            f"{row['completions']:>3} check-offs  best {row['longest_streak']:>2}  ({state})"
        )


def show_struggles(tracker: HabitTracker, today: Optional[date] = None) -> None:
    """Show the habits completed least often over the last month."""
    print(f"\n-- Hardest habits, last {STRUGGLE_WINDOW_DAYS} days --")
    today = today or date.today()
    since = today - timedelta(days=STRUGGLE_WINDOW_DAYS)
    ranked = analytics.struggled_most_since(tracker, since, today)
    if not ranked:
        print("No habits to rank yet.")
        return
    for name, rate in ranked:
        print(f"  {name:<20} completed {rate:.0%} of its periods")


MENU: tuple[tuple[str, Callable[[HabitTracker], None]], ...] = (
    ("Create a habit", create_habit),
    ("Check off a task", check_off),
    ("View all habits", list_all),
    ("View daily habits", lambda tracker: list_by_periodicity(tracker, Periodicity.DAILY)),
    ("View weekly habits", lambda tracker: list_by_periodicity(tracker, Periodicity.WEEKLY)),
    ("Streak for one habit", show_streak_for_habit),
    ("Longest streak overall", show_best_streak),
    ("Statistics", show_statistics),
    ("Hardest habits last month", show_struggles),
    ("Edit a habit", edit_habit),
    ("Delete a habit", delete_habit),
)


def print_menu() -> None:
    """Print the numbered menu."""
    print(f"\n{RULE}")
    print("  HABIT TRACKER")
    print(RULE)
    for number, (label, _action) in enumerate(MENU, start=1):
        print(f"{number:>3}. {label}")
    print(f"{len(MENU) + 1:>3}. Exit")
    print(RULE)


def run(tracker: Optional[HabitTracker] = None) -> None:
    """Run the menu loop until the user exits.

    Args:
        tracker: The tracker to drive. Defaults to one loaded from the standard
            data file.
    """
    try:
        tracker = tracker if tracker is not None else HabitTracker()
    except StorageError as error:
        print(f"Could not start: {error}")
        return

    print(f"Tracking {len(tracker)} habits. Type a number to choose an action.")
    quit_option = str(len(MENU) + 1)

    while True:
        print_menu()
        try:
            choice = ask(f"Choice (1-{quit_option}): ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        if choice == quit_option or choice.lower() in {"q", "quit", "exit"}:
            print("Goodbye.")
            return

        if not choice.isdigit() or not 1 <= int(choice) <= len(MENU):
            print(f"Enter a number between 1 and {quit_option}.")
            continue

        try:
            MENU[int(choice) - 1][1](tracker)
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return
        except StorageError as error:
            print(f"Could not save: {error}")
