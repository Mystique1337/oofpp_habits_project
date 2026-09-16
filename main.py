"""Entry point: wires storage, the tracker and the CLI together.

Run with no arguments to open the menu against `habits_data.json`:

    python main.py

On a first run the file does not exist, so the five predefined habits and their
four weeks of history are written out. `--reset` rewrites them over whatever is
there, which is how to get back to a known state after experimenting.
"""

import argparse
import sys

from cli.interface import run
from fixtures.seed_data import seeded_tracker
from models.tracker import HabitTracker
from storage.json_storage import DEFAULT_DATA_FILE, JsonStorage, StorageError


def parse_args(argv=None) -> argparse.Namespace:
    """Read the command-line arguments."""
    parser = argparse.ArgumentParser(description="Track daily and weekly habits.")
    parser.add_argument(
        "--data-file",
        default=DEFAULT_DATA_FILE,
        help=f"where habits are stored (default: {DEFAULT_DATA_FILE})",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="replace the data file with the five predefined habits and four weeks of data",
    )
    return parser.parse_args(argv)


def load_tracker(data_file: str, reset: bool) -> HabitTracker:
    """Open the tracker, seeding the predefined habits when there is no data yet.

    Raises:
        StorageError: if the data file exists but cannot be read.
    """
    storage = JsonStorage(data_file)
    if reset or not storage.exists():
        tracker = seeded_tracker(storage=storage)
        print(f"Loaded {len(tracker)} predefined habits with four weeks of history.")
        return tracker
    return HabitTracker(storage=storage)


def main(argv=None) -> int:
    """Start the application. Returns the process exit code."""
    args = parse_args(argv)
    try:
        tracker = load_tracker(args.data_file, args.reset)
    except StorageError as error:
        print(f"Could not open {args.data_file}: {error}", file=sys.stderr)
        print("Fix or remove the file, or start elsewhere with --data-file.", file=sys.stderr)
        return 1

    run(tracker)
    return 0


if __name__ == "__main__":
    sys.exit(main())
