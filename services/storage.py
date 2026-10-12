"""Atomowy magazyn JSON + SQLite używany przez całą aplikację."""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any


def _json_safe(value: Any):
    """Nie zapisuje binarnej zawartości plików w rejestrach JSON."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class SharedStateStore:
    def __init__(self, database_path: str, default_directory: str):
        self.database_path = database_path
        self.default_directory = default_directory

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            """CREATE TABLE IF NOT EXISTS application_state (
            state_key TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_epoch REAL NOT NULL
            )"""
        )
        return connection

    def atomic_write_json(self, path: str, data: Any) -> None:
        directory = os.path.dirname(path) or self.default_directory
        os.makedirs(directory, exist_ok=True)
        temporary_path = os.path.join(directory, f".{os.path.basename(path)}.{os.getpid()}.tmp")
        with open(temporary_path, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, default=_json_safe)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)

    def load(self, state_key: str, mirror_path: str, default: Any) -> Any:
        connection = None
        try:
            connection = self._connection()
            row = connection.execute("SELECT payload, updated_epoch FROM application_state WHERE state_key = ?", (state_key,)).fetchone()
            database_value = json.loads(row[0]) if row else default
            database_epoch = float(row[1]) if row else 0.0
            mirror_epoch = os.path.getmtime(mirror_path) if os.path.isfile(mirror_path) else 0.0
            if mirror_epoch > database_epoch:
                try:
                    with open(mirror_path, "r", encoding="utf-8") as stream:
                        mirror_value = json.load(stream)
                    connection.execute(
                        "INSERT OR REPLACE INTO application_state (state_key, payload, updated_epoch) VALUES (?, ?, ?)",
                        (state_key, json.dumps(mirror_value, ensure_ascii=False, default=_json_safe), mirror_epoch),
                    )
                    connection.commit()
                    return mirror_value
                except (OSError, json.JSONDecodeError):
                    pass
            return database_value
        except (sqlite3.Error, TypeError, ValueError, json.JSONDecodeError):
            try:
                with open(mirror_path, "r", encoding="utf-8") as stream:
                    return json.load(stream)
            except (OSError, json.JSONDecodeError):
                return default
        finally:
            if connection is not None:
                connection.close()

    def save(self, state_key: str, mirror_path: str, data: Any) -> None:
        self.atomic_write_json(mirror_path, data)
        mirror_epoch = os.path.getmtime(mirror_path)
        connection = self._connection()
        try:
            connection.execute(
                "INSERT OR REPLACE INTO application_state (state_key, payload, updated_epoch) VALUES (?, ?, ?)",
                (state_key, json.dumps(data, ensure_ascii=False, default=_json_safe), mirror_epoch),
            )
            connection.commit()
        finally:
            connection.close()
