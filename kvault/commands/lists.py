"""List commands: LPUSH RPUSH LPOP RPOP LRANGE LLEN LINDEX LSET LINSERT."""

from __future__ import annotations
from kvault.store import KVStore
from kvault.protocol.encoder import RESPError, OK


def _require(args, n, name):
    if len(args) < n:
        raise RESPError(f"ERR wrong number of arguments for '{name}' command")


def _lpush(store: KVStore, args: list[bytes]):
    _require(args, 2, "LPUSH")
    return store.lpush(args[0].decode(), *args[1:])


def _rpush(store: KVStore, args: list[bytes]):
    _require(args, 2, "RPUSH")
    return store.rpush(args[0].decode(), *args[1:])


def _lpushx(store: KVStore, args: list[bytes]):
    _require(args, 2, "LPUSHX")
    key = args[0].decode()
    if store.key_type(key) == "none":
        return 0
    return store.lpush(key, *args[1:])


def _rpushx(store: KVStore, args: list[bytes]):
    _require(args, 2, "RPUSHX")
    key = args[0].decode()
    if store.key_type(key) == "none":
        return 0
    return store.rpush(key, *args[1:])


def _lpop(store: KVStore, args: list[bytes]):
    _require(args, 1, "LPOP")
    count = int(args[1]) if len(args) > 1 else None
    return store.lpop(args[0].decode(), count)


def _rpop(store: KVStore, args: list[bytes]):
    _require(args, 1, "RPOP")
    count = int(args[1]) if len(args) > 1 else None
    return store.rpop(args[0].decode(), count)


def _lrange(store: KVStore, args: list[bytes]):
    _require(args, 3, "LRANGE")
    return store.lrange(args[0].decode(), int(args[1]), int(args[2]))


def _llen(store: KVStore, args: list[bytes]):
    _require(args, 1, "LLEN")
    return store.llen(args[0].decode())


def _lindex(store: KVStore, args: list[bytes]):
    _require(args, 2, "LINDEX")
    return store.lindex(args[0].decode(), int(args[1]))


def _lset(store: KVStore, args: list[bytes]):
    _require(args, 3, "LSET")
    store.lset(args[0].decode(), int(args[1]), args[2])
    return OK


def _linsert(store: KVStore, args: list[bytes]):
    _require(args, 4, "LINSERT")
    direction = args[1].upper()
    if direction not in (b"BEFORE", b"AFTER"):
        raise RESPError("ERR syntax error")
    return store.linsert(args[0].decode(), direction == b"BEFORE", args[2], args[3])


COMMANDS = {
    "LPUSH": _lpush,
    "RPUSH": _rpush,
    "LPUSHX": _lpushx,
    "RPUSHX": _rpushx,
    "LPOP": _lpop,
    "RPOP": _rpop,
    "LRANGE": _lrange,
    "LLEN": _llen,
    "LINDEX": _lindex,
    "LSET": _lset,
    "LINSERT": _linsert,
}
