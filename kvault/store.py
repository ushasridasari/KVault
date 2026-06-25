"""
Thread-safe in-memory key-value store with TTL support.

Supported value types:
  string  →  bytes
  list    →  collections.deque
  hash    →  dict[str, bytes]
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

# Internal type tags
T_STRING = "string"
T_LIST = "list"
T_HASH = "hash"


class WrongTypeError(Exception):
    """Raised when an operation targets the wrong value type."""

    MSG = "WRONGTYPE Operation against a key holding the wrong kind of value"

    def __init__(self) -> None:
        super().__init__(self.MSG)


class KVStore:
    """
    Core in-memory store.

    All public methods are thread-safe — protected by a single
    re-entrant lock so compound operations (e.g. check-then-set)
    remain atomic.
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}      # key → value
        self._types: dict[str, str] = {}     # key → type tag
        self._expiry: dict[str, float] = {}  # key → absolute epoch (seconds)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_expired(self, key: str) -> bool:
        exp = self._expiry.get(key)
        return exp is not None and time.monotonic() > exp

    def _evict(self, key: str) -> None:
        self._data.pop(key, None)
        self._types.pop(key, None)
        self._expiry.pop(key, None)

    def _check_type(self, key: str, expected: str) -> None:
        t = self._types.get(key)
        if t is not None and t != expected:
            raise WrongTypeError

    def _expire_if_needed(self, key: str) -> bool:
        """Return True (and evict) if the key is expired."""
        if self._is_expired(key):
            self._evict(key)
            return True
        return False

    # ------------------------------------------------------------------
    # Generic key commands
    # ------------------------------------------------------------------

    def exists(self, *keys: str) -> int:
        with self._lock:
            return sum(
                1
                for k in keys
                if k in self._data and not self._expire_if_needed(k)
            )

    def delete(self, *keys: str) -> int:
        with self._lock:
            removed = 0
            for k in keys:
                if k in self._data:
                    self._evict(k)
                    removed += 1
            return removed

    def key_type(self, key: str) -> str:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return "none"
            return self._types[key]

    def keys(self, pattern: str = "*") -> list[str]:
        """Return live keys matching a glob-style *pattern*."""
        import fnmatch
        with self._lock:
            live = [k for k in list(self._data) if not self._expire_if_needed(k)]
            return fnmatch.filter(live, pattern)

    def dbsize(self) -> int:
        with self._lock:
            return sum(
                1 for k in self._data if not self._is_expired(k)
            )

    def flushdb(self) -> None:
        with self._lock:
            self._data.clear()
            self._types.clear()
            self._expiry.clear()

    # ------------------------------------------------------------------
    # TTL / expiry
    # ------------------------------------------------------------------

    def expire(self, key: str, seconds: float) -> int:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return 0
            self._expiry[key] = time.monotonic() + seconds
            return 1

    def expireat(self, key: str, unix_ts: float) -> int:
        """Set expiry to an absolute Unix timestamp (seconds)."""
        delta = unix_ts - time.time()
        return self.expire(key, delta)

    def persist(self, key: str) -> int:
        with self._lock:
            if key not in self._expiry:
                return 0
            del self._expiry[key]
            return 1

    def ttl(self, key: str) -> int:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return -2
            if key not in self._expiry:
                return -1
            remaining = self._expiry[key] - time.monotonic()
            return max(0, int(remaining))

    def pttl(self, key: str) -> int:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return -2
            if key not in self._expiry:
                return -1
            remaining = self._expiry[key] - time.monotonic()
            return max(0, int(remaining * 1000))

    # ------------------------------------------------------------------
    # String commands
    # ------------------------------------------------------------------

    def get(self, key: str) -> bytes | None:
        with self._lock:
            if self._expire_if_needed(key):
                return None
            self._check_type(key, T_STRING)
            return self._data.get(key)

    def set(
        self,
        key: str,
        value: bytes,
        *,
        ex: int | None = None,
        px: int | None = None,
        nx: bool = False,
        xx: bool = False,
        keepttl: bool = False,
    ) -> bool:
        with self._lock:
            exists = key in self._data and not self._expire_if_needed(key)
            if nx and exists:
                return False
            if xx and not exists:
                return False
            self._data[key] = value
            self._types[key] = T_STRING
            if not keepttl:
                self._expiry.pop(key, None)
            if ex is not None:
                self._expiry[key] = time.monotonic() + ex
            elif px is not None:
                self._expiry[key] = time.monotonic() + px / 1000.0
            return True

    def getset(self, key: str, value: bytes) -> bytes | None:
        with self._lock:
            old = self.get(key)
            self.set(key, value)
            return old

    def mget(self, *keys: str) -> list[bytes | None]:
        with self._lock:
            return [self.get(k) for k in keys]

    def mset(self, mapping: dict[str, bytes]) -> None:
        with self._lock:
            for k, v in mapping.items():
                self.set(k, v)

    def msetnx(self, mapping: dict[str, bytes]) -> bool:
        with self._lock:
            for k in mapping:
                if k in self._data and not self._expire_if_needed(k):
                    return False
            for k, v in mapping.items():
                self.set(k, v)
            return True

    def incr(self, key: str, amount: int = 1) -> int:
        return self._incrby(key, amount)

    def decr(self, key: str, amount: int = 1) -> int:
        return self._incrby(key, -amount)

    def _incrby(self, key: str, delta: int) -> int:
        with self._lock:
            self._check_type(key, T_STRING)
            raw = self._data.get(key, b"0")
            if self._expire_if_needed(key):
                raw = b"0"
            try:
                val = int(raw) + delta
            except (ValueError, TypeError):
                raise ValueError("ERR value is not an integer or out of range")
            self._data[key] = str(val).encode()
            self._types[key] = T_STRING
            return val

    def incrbyfloat(self, key: str, amount: float) -> float:
        with self._lock:
            self._check_type(key, T_STRING)
            raw = self._data.get(key, b"0")
            if self._expire_if_needed(key):
                raw = b"0"
            try:
                val = float(raw) + amount
            except (ValueError, TypeError):
                raise ValueError("ERR value is not a valid float")
            # Use repr-like precision to avoid floating-point cruft
            result = f"{val:.17g}"
            self._data[key] = result.encode()
            self._types[key] = T_STRING
            return float(result)

    def append(self, key: str, value: bytes) -> int:
        with self._lock:
            self._check_type(key, T_STRING)
            if self._expire_if_needed(key) or key not in self._data:
                self._data[key] = value
                self._types[key] = T_STRING
            else:
                self._data[key] += value
            return len(self._data[key])

    def strlen(self, key: str) -> int:
        with self._lock:
            if self._expire_if_needed(key):
                return 0
            self._check_type(key, T_STRING)
            return len(self._data.get(key, b""))

    def getrange(self, key: str, start: int, end: int) -> bytes:
        with self._lock:
            if self._expire_if_needed(key):
                return b""
            self._check_type(key, T_STRING)
            val = self._data.get(key, b"")
            length = len(val)
            # Convert negative indices
            if start < 0:
                start = max(0, length + start)
            if end < 0:
                end = length + end
            if start > end or start >= length:
                return b""
            return val[start : end + 1]

    # ------------------------------------------------------------------
    # List commands
    # ------------------------------------------------------------------

    def lpush(self, key: str, *values: bytes) -> int:
        with self._lock:
            self._check_type(key, T_LIST)
            if self._expire_if_needed(key) or key not in self._data:
                self._data[key] = deque()
                self._types[key] = T_LIST
            d: deque = self._data[key]
            for v in values:
                d.appendleft(v)
            return len(d)

    def rpush(self, key: str, *values: bytes) -> int:
        with self._lock:
            self._check_type(key, T_LIST)
            if self._expire_if_needed(key) or key not in self._data:
                self._data[key] = deque()
                self._types[key] = T_LIST
            d: deque = self._data[key]
            for v in values:
                d.append(v)
            return len(d)

    def lpop(self, key: str, count: int | None = None) -> bytes | list | None:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return None
            self._check_type(key, T_LIST)
            d: deque = self._data[key]
            if count is None:
                val = d.popleft() if d else None
            else:
                val = [d.popleft() for _ in range(min(count, len(d)))]
            if not d:
                self._evict(key)
            return val

    def rpop(self, key: str, count: int | None = None) -> bytes | list | None:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return None
            self._check_type(key, T_LIST)
            d: deque = self._data[key]
            if count is None:
                val = d.pop() if d else None
            else:
                val = [d.pop() for _ in range(min(count, len(d)))]
            if not d:
                self._evict(key)
            return val

    def lrange(self, key: str, start: int, stop: int) -> list[bytes]:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return []
            self._check_type(key, T_LIST)
            d: deque = self._data[key]
            items = list(d)
            n = len(items)
            if start < 0:
                start = max(0, n + start)
            if stop < 0:
                stop = n + stop
            return items[start : stop + 1]

    def llen(self, key: str) -> int:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return 0
            self._check_type(key, T_LIST)
            return len(self._data[key])

    def lindex(self, key: str, index: int) -> bytes | None:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return None
            self._check_type(key, T_LIST)
            items = list(self._data[key])
            try:
                return items[index]
            except IndexError:
                return None

    def lset(self, key: str, index: int, value: bytes) -> None:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                raise KeyError("ERR no such key")
            self._check_type(key, T_LIST)
            d: deque = self._data[key]
            items = list(d)
            try:
                items[index] = value
            except IndexError:
                raise IndexError("ERR index out of range")
            self._data[key] = deque(items)

    def linsert(self, key: str, before: bool, pivot: bytes, value: bytes) -> int:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return 0
            self._check_type(key, T_LIST)
            items = list(self._data[key])
            try:
                idx = items.index(pivot)
            except ValueError:
                return -1
            insert_at = idx if before else idx + 1
            items.insert(insert_at, value)
            self._data[key] = deque(items)
            return len(items)

    # ------------------------------------------------------------------
    # Hash commands
    # ------------------------------------------------------------------

    def hset(self, key: str, mapping: dict[str, bytes]) -> int:
        with self._lock:
            self._check_type(key, T_HASH)
            if self._expire_if_needed(key) or key not in self._data:
                self._data[key] = {}
                self._types[key] = T_HASH
            h: dict = self._data[key]
            added = sum(1 for f in mapping if f not in h)
            h.update(mapping)
            return added

    def hget(self, key: str, field: str) -> bytes | None:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return None
            self._check_type(key, T_HASH)
            return self._data[key].get(field)

    def hmget(self, key: str, *fields: str) -> list[bytes | None]:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return [None] * len(fields)
            self._check_type(key, T_HASH)
            h = self._data[key]
            return [h.get(f) for f in fields]

    def hgetall(self, key: str) -> dict[str, bytes]:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return {}
            self._check_type(key, T_HASH)
            return dict(self._data[key])

    def hdel(self, key: str, *fields: str) -> int:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return 0
            self._check_type(key, T_HASH)
            h = self._data[key]
            removed = sum(1 for f in fields if h.pop(f, None) is not None)
            if not h:
                self._evict(key)
            return removed

    def hexists(self, key: str, field: str) -> int:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return 0
            self._check_type(key, T_HASH)
            return 1 if field in self._data[key] else 0

    def hlen(self, key: str) -> int:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return 0
            self._check_type(key, T_HASH)
            return len(self._data[key])

    def hkeys(self, key: str) -> list[str]:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return []
            self._check_type(key, T_HASH)
            return list(self._data[key].keys())

    def hvals(self, key: str) -> list[bytes]:
        with self._lock:
            if self._expire_if_needed(key) or key not in self._data:
                return []
            self._check_type(key, T_HASH)
            return list(self._data[key].values())

    def hincrby(self, key: str, field: str, amount: int) -> int:
        with self._lock:
            self._check_type(key, T_HASH)
            if self._expire_if_needed(key) or key not in self._data:
                self._data[key] = {}
                self._types[key] = T_HASH
            h = self._data[key]
            try:
                val = int(h.get(field, b"0")) + amount
            except (ValueError, TypeError):
                raise ValueError("ERR hash value is not an integer")
            h[field] = str(val).encode()
            return val

    # ------------------------------------------------------------------
    # Snapshot helpers (used by RDB persistence)
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """Return a deep copy of the store state for persistence."""
        with self._lock:
            now = time.monotonic()
            out = {}
            for key, value in list(self._data.items()):
                if key in self._expiry and now > self._expiry[key]:
                    continue  # skip expired
                ttl_left = None
                if key in self._expiry:
                    ttl_left = self._expiry[key] - now
                t = self._types[key]
                if t == T_LIST:
                    value = list(value)
                elif t == T_HASH:
                    value = dict(value)
                out[key] = {"type": t, "value": value, "ttl": ttl_left}
            return out

    def restore_snapshot(self, snap: dict) -> None:
        """Load a snapshot produced by :meth:`snapshot`."""
        with self._lock:
            self._data.clear()
            self._types.clear()
            self._expiry.clear()
            now = time.monotonic()
            for key, meta in snap.items():
                t = meta["type"]
                v = meta["value"]
                ttl = meta.get("ttl")
                if ttl is not None and ttl <= 0:
                    continue  # already expired
                if t == T_LIST:
                    self._data[key] = deque(v)
                elif t == T_HASH:
                    self._data[key] = dict(v)
                else:
                    self._data[key] = v
                self._types[key] = t
                if ttl is not None:
                    self._expiry[key] = now + ttl
