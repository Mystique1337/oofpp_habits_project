"""Reading and writing habits as a single JSON document.

JSON was chosen over SQLite because the data is small, the file stays readable
and hand-editable while marking a portfolio project, and it needs no dependency
beyond the standard library. The `load`/`save` pair is deliberately narrow so a
`SqliteStorage` could satisfy the same two methods.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Iterable

from models.habit import Habit

DEFAULT_DATA_FILE = "habits_data.json"
SCHEMA_VERSION = 1


class StorageError(RuntimeError):
    """Raised when the data file exists but cannot be used."""


class JsonStorage:
    """Persists habits to a JSON file.

    Attributes:
        path: Location of the data file.
    """

    def __init__(self, path: "str | Path" = DEFAULT_DATA_FILE):
        """Point the store at a file. The file is created on first save."""
        self.path = Path(path)

    def exists(self) -> bool:
        """Whether the data file is already on disk."""
        return self.path.is_file()

    def load(self) -> list[Habit]:
        """Read every stored habit.

        Returns:
            The stored habits, or an empty list if the file does not exist yet.

        Raises:
            StorageError: if the file exists but is not readable as habit data.
                Corrupt data is reported rather than silently discarded, so a
                typo in a hand-edited file cannot wipe the user's history.
        """
        if not self.exists():
            return []

        try:
            with self.path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
            return [Habit.from_dict(record) for record in payload["habits"]]
        except json.JSONDecodeError as error:
            raise StorageError(f"{self.path} is not valid JSON: {error}") from error
        except (KeyError, TypeError, ValueError) as error:
            raise StorageError(f"{self.path} is not valid habit data: {error}") from error

    def save(self, habits: Iterable[Habit]) -> None:
        """Write habits to the data file, replacing its contents.

        The write goes to a temporary file in the same directory and is then
        moved into place, so an interrupted save cannot leave a half-written
        file where the user's history used to be.
        """
        payload = {"version": SCHEMA_VERSION, "habits": [habit.to_dict() for habit in habits]}
        self.path.parent.mkdir(parents=True, exist_ok=True)

        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.path.parent or ".",
            prefix=self.path.name,
            suffix=".tmp",
            delete=False,
        )
        try:
            with handle:
                json.dump(payload, handle, indent=2)
            os.replace(handle.name, self.path)
        except OSError:
            Path(handle.name).unlink(missing_ok=True)
            raise
