"""Command-line interface.

The only layer that reads from stdin or writes to stdout. It holds no business
logic: every menu action delegates to `HabitTracker` or to `analytics`, which is
what would let a web or desktop front end replace this package on its own.
"""

from cli.interface import run

__all__ = ["run"]
