"""String commands: GET SET GETSET MGET MSET MSETNX INCR DECR INCRBY DECRBY
INCRBYFLOAT APPEND STRLEN GETRANGE SETRANGE SETNX SETEX PSETEX."""

from __future__ import annotations
from kvault.store import KVStore
from kvault.protocol.encoder import RESPError, OK


def _require(args, n, name):
    if len(args) < n:
        raise RESPError(f"ERR wrong number of arguments for '{name}' command")


def _get(store: KVStore, args: list[bytes]):
    _require(args, 1, "GET")
    return store.get(args[0].decode())


def _set(store: KVStore, args: list[bytes]):
    _require(args, 2, "SET")
    key = args[0].decode()
    value = args[1]
    opts = {a.upper() for a in args[2:]}
    kwargs: dict = {}
    i = 2
    nx = xx = False
    keepttl = False
    while i < len(args):
        opt = args[i].upper()
        if opt == b"NX":
            nx = True
        elif opt == b"XX":
            xx = True
        elif opt == b"KEEPTTL":
            keepttl = True
        elif opt == b"EX" and i + 1 < len(args):
            kwargs["ex"] = int(args[i + 1])
            i += 1
        elif opt == b"PX" and i + 1 < len(args):
            kwargs["px"] = int(args[i + 1])
            i += 1
        i += 1
    ok = store.set(key, value, nx=nx, xx=xx, keepttl=keepttl, **kwargs)
    return OK if ok else None


def _getset(store: KVStore, args: list[bytes]):
    _require(args, 2, "GETSET")
    return store.getset(args[0].decode(), args[1])


def _mget(store: KVStore, args: list[bytes]):
    _require(args, 1, "MGET")
    return store.mget(*[a.decode() for a in args])


def _mset(store: KVStore, args: list[bytes]):
    if len(args) < 2 or len(args) % 2 != 0:
        raise RESPError("ERR wrong number of arguments for 'MSET' command")
    mapping = {args[i].decode(): args[i + 1] for i in range(0, len(args), 2)}
    store.mset(mapping)
    return OK


def _msetnx(store: KVStore, args: list[bytes]):
    if len(args) < 2 or len(args) % 2 != 0:
        raise RESPError("ERR wrong number of arguments for 'MSETNX' command")
    mapping = {args[i].decode(): args[i + 1] for i in range(0, len(args), 2)}
    return 1 if store.msetnx(mapping) else 0


def _incr(store: KVStore, args: list[bytes]):
    _require(args, 1, "INCR")
    return store.incr(args[0].decode())


def _decr(store: KVStore, args: list[bytes]):
    _require(args, 1, "DECR")
    return store.decr(args[0].decode())


def _incrby(store: KVStore, args: list[bytes]):
    _require(args, 2, "INCRBY")
    return store.incr(args[0].decode(), int(args[1]))


def _decrby(store: KVStore, args: list[bytes]):
    _require(args, 2, "DECRBY")
    return store.decr(args[0].decode(), int(args[1]))


def _incrbyfloat(store: KVStore, args: list[bytes]):
    _require(args, 2, "INCRBYFLOAT")
    val = store.incrbyfloat(args[0].decode(), float(args[1]))
    return str(val).encode()


def _append(store: KVStore, args: list[bytes]):
    _require(args, 2, "APPEND")
    return store.append(args[0].decode(), args[1])


def _strlen(store: KVStore, args: list[bytes]):
    _require(args, 1, "STRLEN")
    return store.strlen(args[0].decode())


def _getrange(store: KVStore, args: list[bytes]):
    _require(args, 3, "GETRANGE")
    return store.getrange(args[0].decode(), int(args[1]), int(args[2]))


def _setnx(store: KVStore, args: list[bytes]):
    _require(args, 2, "SETNX")
    ok = store.set(args[0].decode(), args[1], nx=True)
    return 1 if ok else 0


def _setex(store: KVStore, args: list[bytes]):
    _require(args, 3, "SETEX")
    store.set(args[0].decode(), args[2], ex=int(args[1]))
    return OK


def _psetex(store: KVStore, args: list[bytes]):
    _require(args, 3, "PSETEX")
    store.set(args[0].decode(), args[2], px=int(args[1]))
    return OK


COMMANDS = {
    "GET": _get,
    "SET": _set,
    "GETSET": _getset,
    "MGET": _mget,
    "MSET": _mset,
    "MSETNX": _msetnx,
    "INCR": _incr,
    "DECR": _decr,
    "INCRBY": _incrby,
    "DECRBY": _decrby,
    "INCRBYFLOAT": _incrbyfloat,
    "APPEND": _append,
    "STRLEN": _strlen,
    "GETRANGE": _getrange,
    "SETNX": _setnx,
    "SETEX": _setex,
    "PSETEX": _psetex,
}
