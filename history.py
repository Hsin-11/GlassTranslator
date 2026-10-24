from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import HISTORY_DB_PATH, ensure_app_dir


class HistoryManager:
    """Newest-first in-memory session history with optional persistent SQLite storage."""

    def __init__(self, persistent: bool = False) -> None:
        self.items: list[dict[str, Any]] = []
        self.persistent = bool(persistent)
        ensure_app_dir()
        if self.persistent:
            self._init_db()
            self._load_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(HISTORY_DB_PATH)
        connection.execute(
            """CREATE TABLE IF NOT EXISTS history (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                original TEXT NOT NULL,
                translated TEXT NOT NULL,
                mode TEXT NOT NULL,
                favorite INTEGER NOT NULL DEFAULT 0
            )"""
        )
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.commit()

    def _load_db(self) -> None:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT id, timestamp, original, translated, mode, favorite FROM history ORDER BY timestamp DESC"
                ).fetchall()
            self.items = [
                {
                    "id": row[0], "timestamp": row[1], "original": row[2],
                    "translated": row[3], "mode": row[4], "favorite": bool(row[5]),
                }
                for row in rows
            ]
        except sqlite3.Error:
            self.items = []

    def add(self, original: str, translated: str, mode: str) -> dict[str, Any]:
        item = {
            "id": str(uuid4()),
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "original": original,
            "translated": translated,
            "mode": mode,
            "favorite": False,
        }
        self.items.insert(0, item)
        if self.persistent:
            self._persist_item(item)
        return item

    def _persist_item(self, item: dict[str, Any]) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO history (id, timestamp, original, translated, mode, favorite) VALUES (?, ?, ?, ?, ?, ?)",
                    (item["id"], item["timestamp"], item["original"], item["translated"], item["mode"], int(item["favorite"])),
                )
        except sqlite3.Error:
            pass

    def set_favorite(self, item_id: str, favorite: bool) -> None:
        for item in self.items:
            if item["id"] == item_id:
                item["favorite"] = bool(favorite)
                break
        if self.persistent:
            try:
                with self._connect() as connection:
                    connection.execute("UPDATE history SET favorite = ? WHERE id = ?", (int(favorite), item_id))
            except sqlite3.Error:
                pass

    def clear(self) -> None:
        self.items.clear()
        if self.persistent:
            try:
                with self._connect() as connection:
                    connection.execute("DELETE FROM history")
            except sqlite3.Error:
                pass

    def set_persistent(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self.persistent:
            return
        self.persistent = enabled
        if enabled:
            self._init_db()
            try:
                with self._connect() as connection:
                    connection.executemany(
                        "INSERT OR REPLACE INTO history (id, timestamp, original, translated, mode, favorite) VALUES (?, ?, ?, ?, ?, ?)",
                        [
                            (item["id"], item["timestamp"], item["original"], item["translated"], item["mode"], int(item["favorite"]))
                            for item in self.items
                        ],
                    )
            except sqlite3.Error:
                pass
        else:
            # Persistent history is explicitly opt-in; disabling it also removes its stored records.
            try:
                if HISTORY_DB_PATH.exists():
                    HISTORY_DB_PATH.unlink()
            except OSError:
                try:
                    with self._connect() as connection:
                        connection.execute("DELETE FROM history")
                except sqlite3.Error:
                    pass
