"""
Command dispatcher.  Maps command name → handler callable.

Each handler has the signature:
    handler(store: KVStore, args: list[bytes]) -> Any

The return value is encoded to RESP by the connection handler.
"""

from __future__ import annotations

from typing import Callable, Any

from kvault.store import KVStore
from kvault.protocol.encoder import RESPError
from . import strings, keys, lists, hashes, server_cmds

Handler = Callable[[KVStore, list[bytes]], Any]


class CommandRegistry:
    def __init__(self) -> None:
        self._table: dict[str, Handler] = {}
        self._register_all()

    def dispatch(self, store: KVStore, raw: list[bytes]) -> Any:
        if not raw:
            return RESPError("ERR empty command")
        name = raw[0].upper().decode("utf-8", errors="replace")
        handler = self._table.get(name)
        if handler is None:
            return RESPError(f"ERR unknown command '{name}'")
        try:
            return handler(store, raw[1:])
        except RESPError as e:
            return e
        except WrongTypeError:
            from kvault.store import WrongTypeError as WTE
            return RESPError(WTE.MSG)
        except (ValueError, TypeError, KeyError, IndexError) as e:
            return RESPError(str(e))

    def _register(self, name: str, handler: Handler) -> None:
        self._table[name.upper()] = handler

    def _register_all(self) -> None:
        # server / connection
        for name, fn in server_cmds.COMMANDS.items():
            self._register(name, fn)
        # strings
        for name, fn in strings.COMMANDS.items():
            self._register(name, fn)
        # keys
        for name, fn in keys.COMMANDS.items():
            self._register(name, fn)
        # lists
        for name, fn in lists.COMMANDS.items():
            self._register(name, fn)
        # hashes
        for name, fn in hashes.COMMANDS.items():
            self._register(name, fn)
