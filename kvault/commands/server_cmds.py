"""Server / connection-level commands: PING, ECHO, INFO, DBSIZE, FLUSHDB, COMMAND."""

from __future__ import annotations
from kvault.store import KVStore
from kvault.protocol.encoder import RESPOk, OK


def _ping(store: KVStore, args: list[bytes]):
    if args:
        return args[0]
    return "PONG"


def _echo(store: KVStore, args: list[bytes]):
    _require(args, 1, "ECHO")
    return args[0]


def _dbsize(store: KVStore, args: list[bytes]):
    return store.dbsize()


def _flushdb(store: KVStore, args: list[bytes]):
    store.flushdb()
    return OK


def _command(store: KVStore, args: list[bytes]):
    return "OK"


def _require(args, n, name):
    if len(args) < n:
        from kvault.protocol.encoder import RESPError
        raise RESPError(f"ERR wrong number of arguments for '{name}' command")


COMMANDS = {
    "PING": _ping,
    "ECHO": _echo,
    "DBSIZE": _dbsize,
    "FLUSHDB": _flushdb,
    "COMMAND": _command,
}
