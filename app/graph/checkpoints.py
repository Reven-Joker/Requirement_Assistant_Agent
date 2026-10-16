"""LangGraph checkpoint factory with SQLite persistence fallback."""

from __future__ import annotations

import pickle
import sqlite3
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from app.core.config import get_settings
from app.core.logger import logger

# Register custom types to suppress msgpack deserialization warnings


def _make_default_serde():
    """Create the default serde with custom types allowed."""
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    serde = JsonPlusSerializer()
    return serde.with_msgpack_allowlist([("app.schemas.review", "ReviewTargetType")])


class PersistentMemorySaver(MemorySaver):
    """MemorySaver-compatible checkpointer that snapshots storage to SQLite.

    The installed LangGraph version in this project does not ship the optional
    sqlite checkpointer package, so this class keeps the official MemorySaver
    behavior and persists its internal checkpoint dictionaries after writes.
    """

    def __init__(self, path: Path, *, serde: Any | None = None) -> None:
        if serde is None:
            serde = _make_default_serde()
        super().__init__(serde=serde)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()
        self._load()

    def put(self, config, checkpoint, metadata, new_versions):  # type: ignore[override]
        with self._lock:
            result = super().put(config, checkpoint, metadata, new_versions)
            self._persist()
            return result

    def put_writes(self, config, writes, task_id, task_path: str = "") -> None:  # type: ignore[override]
        with self._lock:
            super().put_writes(config, writes, task_id, task_path)
            self._persist()

    def delete_thread(self, thread_id: str) -> None:
        with self._lock:
            super().delete_thread(thread_id)
            self._persist()

    def has_thread(self, thread_id: str) -> bool:
        return bool(self.storage.get(thread_id))

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS langgraph_checkpoint_store (
                    key TEXT PRIMARY KEY,
                    value BLOB NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def _load(self) -> None:
        with sqlite3.connect(self.path) as conn:
            rows = dict(conn.execute("SELECT key, value FROM langgraph_checkpoint_store"))
        if not rows:
            return
        try:
            storage = pickle.loads(rows.get("storage", b""))
            writes = pickle.loads(rows.get("writes", b""))
            blobs = pickle.loads(rows.get("blobs", b""))
        except Exception as exc:
            logger.warning(f"Failed to load persisted LangGraph checkpoints: {exc}")
            return

        self.storage = _restore_storage(storage)
        self.writes = defaultdict(dict, writes or {})
        self.blobs = dict(blobs or {})

    def _persist(self) -> None:
        payloads = {
            "storage": pickle.dumps(_plain_dict(self.storage)),
            "writes": pickle.dumps(dict(self.writes)),
            "blobs": pickle.dumps(dict(self.blobs)),
        }
        with sqlite3.connect(self.path) as conn:
            conn.executemany(
                """
                INSERT INTO langgraph_checkpoint_store(key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                list(payloads.items()),
            )
            conn.commit()


_checkpointer: PersistentMemorySaver | MemorySaver | None = None


def get_checkpoint_path() -> Path:
    settings = get_settings()
    return settings.checkpoint_dir / "langgraph_checkpoints.sqlite"


def get_checkpointer() -> PersistentMemorySaver | MemorySaver:
    """Return the process-wide checkpointer."""
    global _checkpointer
    if _checkpointer is None:
        try:
            _checkpointer = PersistentMemorySaver(get_checkpoint_path())
        except Exception as exc:  # pragma: no cover - last-resort fallback
            logger.warning(f"Persistent checkpointer unavailable, using MemorySaver: {exc}")
            _checkpointer = MemorySaver(serde=_make_default_serde())
    return _checkpointer


def reset_checkpointer_for_tests() -> None:
    """Drop the cached checkpointer so tests can simulate a process restart."""
    global _checkpointer
    _checkpointer = None


def has_checkpoint(thread_id: str) -> bool:
    saver = get_checkpointer()
    if hasattr(saver, "has_thread"):
        return bool(saver.has_thread(thread_id))  # type: ignore[attr-defined]
    try:
        return saver.get_tuple({"configurable": {"thread_id": thread_id}}) is not None
    except Exception:
        return False


def _plain_dict(value: Any) -> Any:
    if isinstance(value, defaultdict):
        value = dict(value)
    if isinstance(value, dict):
        return {key: _plain_dict(item) for key, item in value.items()}
    return value


def _restore_storage(value: dict | None):
    restored = defaultdict(lambda: defaultdict(dict))
    for thread_id, namespaces in (value or {}).items():
        restored[thread_id] = defaultdict(dict, namespaces)
    return restored
