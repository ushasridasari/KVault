"""Hash commands: HSET HGET HMGET HMSET HGETALL HDEL HEXISTS HLEN HKEYS HVALS HINCRBY."""

from __future__ import annotations
from kvault.store import KVStore
from kvault.protocol.encoder import RESPError, OK


def _require(args, n, name):
    if len(args) < n:
        raise RESPError(f"ERR wrong number of arguments for '{name}' command")


def _hset(store: KVStore, args: list[bytes]):
    # HSET key field value [field value ...]
    if len(args) < 3 or len(args) % 2 == 0:
        raise RESPError("ERR wrong number of arguments for 'HSET' command")
    key = args[0].decode()
    mapping = {args[i].decode(): args[i + 1] for i in range(1, len(args), 2)}
    return store.hset(key, mapping)


def _hget(store: KVStore, args: list[bytes]):
    _require(args, 2, "HGET")
    return store.hget(args[0].decode(), args[1].decode())


def _hmget(store: KVStore, args: list[bytes]):
    _require(args, 2, "HMGET")
    return store.hmget(args[0].decode(), *[a.decode() for a in args[1:]])


def _hmset(store: KVStore, args: list[bytes]):
    if len(args) < 3 or len(args) % 2 == 0:
        raise RESPError("ERR wrong number of arguments for 'HMSET' command")
    key = args[0].decode()
    mapping = {args[i].decode(): args[i + 1] for i in range(1, len(args), 2)}
    store.hset(key, mapping)
    return OK


def _hgetall(store: KVStore, args: list[bytes]):
    _require(args, 1, "HGETALL")
    h = store.hgetall(args[0].decode())
    # Flatten to alternating field/value list (Redis wire format)
    result = []
    for field, val in h.items():
        result.append(field.encode())
        result.append(val)
    return result


def _hdel(store: KVStore, args: list[bytes]):
    _require(args, 2, "HDEL")
    return store.hdel(args[0].decode(), *[a.decode() for a in args[1:]])


def _hexists(store: KVStore, args: list[bytes]):
    _require(args, 2, "HEXISTS")
    return store.hexists(args[0].decode(), args[1].decode())


def _hlen(store: KVStore, args: list[bytes]):
    _require(args, 1, "HLEN")
    return store.hlen(args[0].decode())


def _hkeys(store: KVStore, args: list[bytes]):
    _require(args, 1, "HKEYS")
    return [k.encode() for k in store.hkeys(args[0].decode())]


def _hvals(store: KVStore, args: list[bytes]):
    _require(args, 1, "HVALS")
    return store.hvals(args[0].decode())


def _hincrby(store: KVStore, args: list[bytes]):
    _require(args, 3, "HINCRBY")
    return store.hincrby(args[0].decode(), args[1].decode(), int(args[2]))


COMMANDS = {
    "HSET": _hset,
    "HGET": _hget,
    "HMGET": _hmget,
    "HMSET": _hmset,
    "HGETALL": _hgetall,
    "HDEL": _hdel,
    "HEXISTS": _hexists,
    "HLEN": _hlen,
    "HKEYS": _hkeys,
    "HVALS": _hvals,
    "HINCRBY": _hincrby,
}
