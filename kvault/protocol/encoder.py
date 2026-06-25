"""
RESP v2 encoder — Python objects → wire bytes.

Mapping:
  None            →  Null bulk string  ($-1\r\n)
  bool            →  Integer  (True=1, False=0)
  int             →  Integer  (:n\r\n)
  str             →  Bulk String
  bytes           →  Bulk String
  list / tuple    →  Array
  RESPError       →  Error   (-msg\r\n)
  RESPOk          →  Simple String  (+OK\r\n)
"""

from __future__ import annotations
from .parser import RESPError

CRLF = b"\r\n"


class RESPOk:
    """Sentinel that encodes as a RESP Simple String '+OK'."""

    _instance: "RESPOk | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "RESPOk()"


OK = RESPOk()


class RESPEncoder:
    """Stateless RESP encoder."""

    @classmethod
    def encode(cls, value: object) -> bytes:
        """Encode *value* to RESP wire bytes."""
        if value is None:
            return b"$-1\r\n"
        if isinstance(value, RESPError):
            return f"-{value.message}\r\n".encode()
        if isinstance(value, RESPOk):
            return b"+OK\r\n"
        if isinstance(value, bool):
            # must come before int check — bool subclasses int
            return f":{int(value)}\r\n".encode()
        if isinstance(value, int):
            return f":{value}\r\n".encode()
        if isinstance(value, str):
            encoded = value.encode("utf-8")
            return b"$" + str(len(encoded)).encode() + CRLF + encoded + CRLF
        if isinstance(value, bytes):
            return b"$" + str(len(value)).encode() + CRLF + value + CRLF
        if isinstance(value, (list, tuple)):
            parts = [b"*" + str(len(value)).encode() + CRLF]
            for item in value:
                parts.append(cls.encode(item))
            return b"".join(parts)
        raise TypeError(f"Cannot encode type {type(value).__name__!r} to RESP")

    @classmethod
    def simple_string(cls, s: str) -> bytes:
        return f"+{s}\r\n".encode()

    @classmethod
    def error(cls, msg: str) -> bytes:
        return f"-{msg}\r\n".encode()

    @classmethod
    def null_array(cls) -> bytes:
        return b"*-1\r\n"
