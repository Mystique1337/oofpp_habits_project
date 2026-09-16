"""Tests for the analytics module, one class per public function.

Two things are checked throughout. First the values, against the four-week
fixture whose expected streaks are pinned in `fixtures.seed_data`. Second the
purity the brief asks for: a function that claims to be pure is called and the
habits it was given are then checked for damage.
"""

import unittest
from datetime import date, timedelta

import analytics
from fixtures.seed_data import (
    EXPECTED_CURRENT_STREAKS,
    EXPECTED_LONGEST_STREAKS,
    build_seed_habits,
)
from models.habit import Habit
from models.periodicity import Periodicity
from tests import FIXED_END_DATE


class AnalyticsTestCase(unittest.TestCase):
    """Base case providing the four-week fixture at a fixed date."""

    def setUp(self):
        self.habits = build_seed_habits(FIXED_END_DATE)
        self.today = FIXED_END_DATE
        self.month_ago = FIXED_END_DATE - timedelta(days=30)

    def snapshot(self) -> list:
        """The habits' observable state, for proving a function did not mutate."""
        return [
            (h.name, h.description, h.periodicity, h.created_at, tuple(h.completions))
            for h in self.habits
        ]


class AllHabitNamesTests(AnalyticsTestCase):
    """`all_habit_names` lists everything currently tracked."""

    def test_it_returns_every_name(self):
        self.assertEqual(
            analytics.all_habit_names(self.habits),
            ["Morning Exercise", "Read", "Meditate", "Weekly Review", "Team Meeting"],
        )

    def test_it_preserves_order(self):
        self.assertEqual(analytics.all_habit_names(self.habits)[0], self.habits[0].name)

    def test_no_habits_gives_an_empty_list(self):
        self.assertEqual(analytics.all_habit_names([]), [])

    def test_it_does_not_mutate_its_input(self):
        before = self.snapshot()
        analytics.all_habit_names(self.habits)
        self.assertEqual(self.snapshot(), before)


class HabitsByPeriodicityTests(AnalyticsTestCase):
    """`habits_by_periodicity` and its name-only companion filter by period."""

    def test_the_daily_habits_are_returned(self):
        self.assertEqual(
            analytics.habit_names_by_periodicity(self.habits, "daily"),
            ["Morning Exercise", "Read", "Meditate"],
        )

    def test_the_weekly_habits_are_returned(self):
        self.assertEqual(
            analytics.habit_names_by_periodicity(self.habits, "weekly"),
            ["Weekly Review", "Team Meeting"],
        )

    def test_the_two_groups_partition_the_whole_set(self):
        daily = analytics.habits_by_periodicity(self.habits, "daily")
        weekly = analytics.habits_by_periodicity(self.habits, "weekly")
        self.assertEqual(len(daily) + len(weekly), len(self.habits))

    def test_it_returns_habits_not_names(self):
        self.assertIsInstance(analytics.habits_by_periodicity(self.habits, "daily")[0], Habit)

    def test_it_accepts_the_enum_as_well_as_a_string(self):
        self.assertEqual(
            analytics.habits_by_periodicity(self.habits, Periodicity.DAILY),
            analytics.habits_by_periodicity(self.habits, "daily"),
        )

    def test_an_unsupported_periodicity_is_reported(self):
        with self.assertRaises(ValueError):
            analytics.habits_by_periodicity(self.habits, "monthly")

    def test_no_habits_gives_an_empty_list(self):
        self.assertEqual(analytics.habits_by_periodicity([], "daily"), [])

    def test_it_does_not_mutate_its_input(self):
        before = self.snapshot()
        analytics.habits_by_periodicity(self.habits, "daily")
        self.assertEqual(self.snapshot(), before)


class LongestStreakAllTests(AnalyticsTestCase):
    """`longest_streak_all` finds the best run across every habit."""

    def test_it_names_the_record_holder_and_the_length(self):
        self.assertEqual(analytics.longest_streak_all(self.habits), ("Morning Exercise", 28))

    def test_it_compares_by_streak_not_by_name(self):
        # The alphabetically last habit holds the shortest streak, so a
        # comparison that fell back to the name would pick the wrong one.
        self.assertNotEqual(analytics.longest_streak_all(self.habits)[0], "Weekly Review")

    def test_daily_and_weekly_habits_are_compared_on_period_counts(self):
        weekly = analytics.habits_by_periodicity(self.habits, "weekly")
        self.assertEqual(analytics.longest_streak_all(weekly), ("Weekly Review", 4))

    def test_no_habits_gives_no_record_holder(self):
        self.assertEqual(analytics.longest_streak_all([]), (None, 0))

    def test_habits_never_checked_off_give_a_zero_streak(self):
        blank = [Habit("Untouched", "never done", "daily")]
        self.assertEqual(analytics.longest_streak_all(blank), ("Untouched", 0))

    def test_the_first_habit_wins_a_tie(self):
        tied = analytics.habits_by_periodicity(self.habits, "daily")[:1] * 2
        self.assertEqual(analytics.longest_streak_all(tied)[0], "Morning Exercise")

    def test_it_does_not_mutate_its_input(self):
        before = self.snapshot()
        analytics.longest_streak_all(self.habits)
        self.assertEqual(self.snapshot(), before)


class LongestStreakForTests(AnalyticsTestCase):
    """`longest_streak_for` reports one habit's best run."""

    def test_every_seeded_habit_matches_its_expected_streak(self):
        for name, expected in EXPECTED_LONGEST_STREAKS.items():
            with self.subTest(habit=name):
                self.assertEqual(analytics.longest_streak_for(self.habits, name), expected)

    def test_the_name_is_matched_case_insensitively(self):
        self.assertEqual(analytics.longest_streak_for(self.habits, "  read "), 8)

    def test_it_reports_the_best_run_not_the_current_one(self):
        # Meditate has lapsed, so its current streak is 0 but its record stands.
        self.assertEqual(analytics.longest_streak_for(self.habits, "Meditate"), 11)

    def test_an_unknown_habit_is_reported_rather_than_scored_zero(self):
        with self.assertRaises(KeyError):
            analytics.longest_streak_for(self.habits, "Nothing")

    def test_it_does_not_mutate_its_input(self):
        before = self.snapshot()
        analytics.longest_streak_for(self.habits, "Read")
        self.assertEqual(self.snapshot(), before)


class CurrentStreaksTests(AnalyticsTestCase):
    """`current_streaks` reports where every habit stands today."""

    def test_every_seeded_habit_matches_its_expected_current_streak(self):
        self.assertEqual(
            analytics.current_streaks(self.habits, self.today), EXPECTED_CURRENT_STREAKS
        )

    def test_a_lapsed_habit_reports_zero(self):
        self.assertEqual(analytics.current_streaks(self.habits, self.today)["Meditate"], 0)

    def test_the_reference_date_moves_the_answer(self):
        much_later = analytics.current_streaks(self.habits, self.today + timedelta(days=60))
        self.assertEqual(set(much_later.values()), {0})

    def test_no_habits_gives_an_empty_mapping(self):
        self.assertEqual(analytics.current_streaks([], self.today), {})


class CompletionTotalsTests(AnalyticsTestCase):
    """`completion_totals` counts raw check-offs, not periods."""

    def test_a_perfect_daily_habit_has_one_per_day(self):
        self.assertEqual(analytics.completion_totals(self.habits)["Morning Exercise"], 28)

    def test_repeats_inside_a_period_are_still_counted(self):
        # Team Meeting has 4 check-offs across 3 distinct weeks.
        self.assertEqual(analytics.completion_totals(self.habits)["Team Meeting"], 4)
        self.assertEqual(analytics.longest_streak_for(self.habits, "Team Meeting"), 2)

    def test_every_habit_appears(self):
        self.assertEqual(len(analytics.completion_totals(self.habits)), len(self.habits))


class CompletionRateTests(AnalyticsTestCase):
    """`completion_rate` measures how much of a window was covered."""

    def test_a_perfect_daily_habit_scores_one(self):
        exercise = self.habits[0]
        window_start = self.today - timedelta(days=27)
        self.assertEqual(analytics.completion_rate(exercise, window_start, self.today), 1.0)

    def test_a_habit_with_gaps_scores_below_one(self):
        reading = self.habits[1]
        window_start = self.today - timedelta(days=27)
        self.assertAlmostEqual(analytics.completion_rate(reading, window_start, self.today), 25 / 28)

    def test_a_single_day_window_is_all_or_nothing(self):
        exercise = self.habits[0]
        self.assertEqual(analytics.completion_rate(exercise, self.today, self.today), 1.0)

    def test_an_inverted_window_scores_zero(self):
        exercise = self.habits[0]
        self.assertEqual(analytics.completion_rate(exercise, self.today, self.month_ago), 0.0)

    def test_a_weekly_habit_is_measured_in_weeks(self):
        review = self.habits[3]
        window_start = self.today - timedelta(days=21)
        self.assertEqual(analytics.completion_rate(review, window_start, self.today), 1.0)


class StruggledMostSinceTests(AnalyticsTestCase):
    """`struggled_most_since` answers "which habits did I struggle with?"."""

    def test_the_worst_habit_comes_first(self):
        ranked = analytics.struggled_most_since(self.habits, self.month_ago, self.today)
        self.assertEqual(ranked[0][0], "Meditate")

    def test_results_are_ordered_worst_first(self):
        ranked = analytics.struggled_most_since(self.habits, self.month_ago, self.today, limit=5)
        rates = [rate for _name, rate in ranked]
        self.assertEqual(rates, sorted(rates))

    def test_the_limit_is_respected(self):
        ranked = analytics.struggled_most_since(self.habits, self.month_ago, self.today, limit=2)
        self.assertEqual(len(ranked), 2)

    def test_the_perfect_habit_is_not_in_the_worst_three(self):
        ranked = analytics.struggled_most_since(self.habits, self.month_ago, self.today)
        self.assertNotIn("Morning Exercise", [name for name, _rate in ranked])

    def test_habits_created_after_the_window_are_left_out(self):
        newcomer = Habit("Brand New", "just started", "daily")
        ranked = analytics.struggled_most_since(
            self.habits + [newcomer], self.month_ago, self.today, limit=10
        )
        self.assertNotIn("Brand New", [name for name, _rate in ranked])

    def test_no_habits_gives_an_empty_ranking(self):
        self.assertEqual(analytics.struggled_most_since([], self.month_ago, self.today), [])

    def test_it_does_not_mutate_its_input(self):
        before = self.snapshot()
        analytics.struggled_most_since(self.habits, self.month_ago, self.today)
        self.assertEqual(self.snapshot(), before)


class SummariseTests(AnalyticsTestCase):
    """`summarise` is the one call behind the CLI statistics screen."""

    def setUp(self):
        super().setUp()
        self.report = analytics.summarise(self.habits, self.today)

    def test_the_totals_are_counted(self):
        self.assertEqual(self.report["total_habits"], 5)
        self.assertEqual(self.report["daily_habits"], 3)
        self.assertEqual(self.report["weekly_habits"], 2)

    def test_the_record_holder_is_named(self):
        self.assertEqual(self.report["best_habit"], "Morning Exercise")
        self.assertEqual(self.report["best_streak"], 28)

    def test_every_habit_gets_a_row(self):
        self.assertEqual(
            [row["name"] for row in self.report["habits"]],
            analytics.all_habit_names(self.habits),
        )

    def test_each_row_carries_both_streaks(self):
        row = next(r for r in self.report["habits"] if r["name"] == "Meditate")
        self.assertEqual(row["longest_streak"], 11)
        self.assertEqual(row["current_streak"], 0)

    def test_a_lapsed_habit_is_flagged_as_broken(self):
        broken = {row["name"] for row in self.report["habits"] if row["broken"]}
        self.assertEqual(broken, {"Meditate"})

    def test_the_report_is_json_friendly(self):
        import json

        self.assertIsInstance(json.dumps(self.report), str)

    def test_an_empty_tracker_summarises_without_error(self):
        empty = analytics.summarise([], self.today)
        self.assertEqual(empty["total_habits"], 0)
        self.assertIsNone(empty["best_habit"])

    def test_it_does_not_mutate_its_input(self):
        before = self.snapshot()
        analytics.summarise(self.habits, self.today)
        self.assertEqual(self.snapshot(), before)


class SeedFixtureTests(unittest.TestCase):
    """The four-week fixture itself, checked before anything relies on it."""

    def test_there_are_five_predefined_habits(self):
        self.assertEqual(len(build_seed_habits(FIXED_END_DATE)), 5)

    def test_both_periodicities_are_represented(self):
        habits = build_seed_habits(FIXED_END_DATE)
        self.assertEqual(len(analytics.habits_by_periodicity(habits, "daily")), 3)
        self.assertEqual(len(analytics.habits_by_periodicity(habits, "weekly")), 2)

    def test_the_data_spans_four_weeks(self):
        habits = build_seed_habits(FIXED_END_DATE)
        dates = [d for habit in habits for d in habit.completion_dates()]
        self.assertEqual((max(dates) - min(dates)).days, 27)

    def test_no_check_off_is_dated_in_the_future(self):
        habits = build_seed_habits(FIXED_END_DATE)
        latest = max(d for habit in habits for d in habit.completion_dates())
        self.assertLessEqual(latest, FIXED_END_DATE)

    def test_the_streaks_hold_whatever_weekday_the_data_ends_on(self):
        # The weekly patterns are anchored to a Monday, so they must survive the
        # fixture being built on any day of the week.
        for offset in range(7):
            end = date(2026, 3, 2) + timedelta(days=offset)
            with self.subTest(weekday=end.strftime("%A")):
                for habit in build_seed_habits(end):
                    self.assertEqual(
                        habit.longest_streak(), EXPECTED_LONGEST_STREAKS[habit.name]
                    )
                    self.assertEqual(
                        habit.current_streak(end), EXPECTED_CURRENT_STREAKS[habit.name]
                    )


if __name__ == "__main__":
    unittest.main()
