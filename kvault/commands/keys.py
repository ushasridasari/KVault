"""Generic key commands: DEL EXISTS TYPE KEYS RENAME EXPIRE TTL PTTL PERSIST EXPIREAT."""

from __future__ import annotations
from kvault.store import KVStore
from kvault.protocol.encoder import RESPError, OK


def _require(args, n, name):
    if len(args) < n:
        raise RESPError(f"ERR wrong number of arguments for '{name}' command")


def _del(store: KVStore, args: list[bytes]):
    _require(args, 1, "DEL")
    return store.delete(*[a.decode() for a in args])


def _exists(store: KVStore, args: list[bytes]):
    _require(args, 1, "EXISTS")
    return store.exists(*[a.decode() for a in args])


def _type(store: KVStore, args: list[bytes]):
    _require(args, 1, "TYPE")
    return store.key_type(args[0].decode())


def _keys(store: KVStore, args: list[bytes]):
    _require(args, 1, "KEYS")
    pattern = args[0].decode()
    return store.keys(pattern)


def _rename(store: KVStore, args: list[bytes]):
    _require(args, 2, "RENAME")
    src, dst = args[0].decode(), args[1].decode()
    val = store.get(src)
    if val is None:
        # Check if it's a list or hash
        t = store.key_type(src)
        if t == "none":
            raise RESPError("ERR no such key")
    # Copy raw internals via snapshot manipulation — simpler approach:
    snap = store.snapshot()
    if src not in snap:
        raise RESPError("ERR no such key")
    meta = snap[src]
    store.delete(dst)
    store._lock.acquire()
    try:
        from kvault.store import T_STRING, T_LIST, T_HASH
        from collections import deque
        import time
        t = meta["type"]
        v = meta["value"]
        ttl = meta.get("ttl")
        if t == T_LIST:
            store._data[dst] = deque(v)
        elif t == T_HASH:
            store._data[dst] = dict(v)
        else:
            store._data[dst] = v
        store._types[dst] = t
        store._expiry.pop(dst, None)
        if ttl is not None and ttl > 0:
            store._expiry[dst] = time.monotonic() + ttl
        store.delete(src)
    finally:
        store._lock.release()
    return OK


def _expire(store: KVStore, args: list[bytes]):
    _require(args, 2, "EXPIRE")
    return store.expire(args[0].decode(), int(args[1]))


def _pexpire(store: KVStore, args: list[bytes]):
    _require(args, 2, "PEXPIRE")
    return store.expire(args[0].decode(), int(args[1]) / 1000.0)


def _expireat(store: KVStore, args: list[bytes]):
    _require(args, 2, "EXPIREAT")
    return store.expireat(args[0].decode(), int(args[1]))

def _persist(store: KVStore, args: list[bytes]):
    _require(args, 1, "PERSIST")
    return store.persist(args[0].decode())


def _ttl(store: KVStore, args: list[bytes]):
    _require(args, 1, "TTL")
    return store.ttl(args[0].decode())


def _pttl(store: KVStore, args: list[bytes]):
    _require(args, 1, "PTTL")
    return store.pttl(args[0].decode())


COMMANDS = {
    "DEL": _del,
    "EXISTS": _exists,
    "TYPE": _type,
    "KEYS": _keys,
    "RENAME": _rename,
    "EXPIRE": _expire,
    "PEXPIRE": _pexpire,
    "EXPIREAT": _expireat,
    "PERSIST": _persist,
    "TTL": _ttl,
    "PTTL": _pttl,
}
