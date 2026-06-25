"""
RDB-style snapshot persistence.

The snapshot is stored as a gzip-compressed JSON file.  While this is
not binary-compatible with Redis .rdb files, it is human-inspectable
and sufficient for an MS project demonstrating persistence semantics.

Save strategy:
  - Background save: runs in a daemon thread to avoid blocking the event loop.
  - Auto-save: optional interval-based saves (disabled by default).
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kvault.store import KVStore

log = logging.getLogger(__name__)

DEFAULT_PATH = Path("kvault_dump.rdb")


class _JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            return {"__bytes__": obj.hex()}
        return super().default(obj)


def _json_decoder(dct: dict):
    if "__bytes__" in dct:
        return bytes.fromhex(dct["__bytes__"])
    return dct


class RDBSnapshot:
    """Manages background save / load of the KV store to disk."""

    def __init__(self, store: "KVStore", path: Path | str = DEFAULT_PATH) -> None:
        self._store = store
        self._path = Path(path)
        self._lock = threading.Lock()
        self._save_thread: threading.Thread | None = None
        self._auto_save_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Synchronous (blocking) save."""
        self._write_snapshot()

    def bgsave(self) -> str:
        """Non-blocking background save; returns immediately."""
        with self._lock:
            if self._save_thread and self._save_thread.is_alive():
                return "Background save already in progress"
            self._save_thread = threading.Thread(
                target=self._write_snapshot, daemon=True, name="kvault-bgsave"
            )
            self._save_thread.start()
        return "Background saving started"

    def _write_snapshot(self) -> None:
        snap = self._store.snapshot()
        tmp = self._path.with_suffix(".rdb.tmp")
        try:
            with gzip.open(tmp, "wt", encoding="utf-8") as f:
                json.dump(snap, f, cls=_JSONEncoder)
            tmp.replace(self._path)
            log.info("Snapshot saved → %s", self._path)
        except Exception:
            log.exception("Failed to write snapshot")
            tmp.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Load the on-disk snapshot into the store.  Returns True on success."""
        if not self._path.exists():
            log.info("No snapshot found at %s — starting fresh", self._path)
            return False
        try:
            with gzip.open(self._path, "rt", encoding="utf-8") as f:
                snap = json.load(f, object_hook=_json_decoder)
            self._store.restore_snapshot(snap)
            log.info("Snapshot loaded ← %s (%d keys)", self._path, len(snap))
            return True
        except Exception:
            log.exception("Failed to load snapshot from %s", self._path)
            return False

    # ------------------------------------------------------------------
    # Auto-save
    # ------------------------------------------------------------------

    def start_auto_save(self, interval_seconds: int = 300) -> None:
        """Periodically save in the background every *interval_seconds*."""
        self._stop_event.clear()
        self._auto_save_thread = threading.Thread(
            target=self._auto_save_loop,
            args=(interval_seconds,),
            daemon=True,
            name="kvault-autosave",
        )
        self._auto_save_thread.start()
        log.info("Auto-save enabled every %ds", interval_seconds)

    def stop_auto_save(self) -> None:
        self._stop_event.set()

    def _auto_save_loop(self, interval: int) -> None:
        while not self._stop_event.wait(interval):
            self._write_snapshot()
