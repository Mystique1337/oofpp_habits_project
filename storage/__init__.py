"""Persistence layer.

Everything that touches the filesystem lives here, so swapping the JSON file for
SQLite means adding a module beside `json_storage` and changing nothing else.
"""

from storage.json_storage import JsonStorage, StorageError

__all__ = ["JsonStorage", "StorageError"]
