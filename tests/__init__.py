"""Unit tests.

Written with `unittest` from the standard library so the suite runs on a clean
Python install with nothing to install first:

    python -m unittest discover -s tests -v

`pytest` will collect and run these same tests unchanged if it is available.
"""

from datetime import date

FIXED_END_DATE = date(2026, 3, 4)
"""Anchor date for every test that touches the four-week fixture.

Pinning it keeps the expected streaks constant: a test that built its data
relative to `date.today()` would pass or fail depending on the weekday it ran.
2026-03-04 is a Wednesday, chosen so the weekly patterns have days on both
sides of it inside the same week.
"""
