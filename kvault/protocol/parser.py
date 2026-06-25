"""
RESP (REdis Serialization Protocol) v2 parser.

Wire types:
  +  Simple String   →  str
  -  Error           →  RESPError
  :  Integer         →  int
  $  Bulk String     →  bytes | None
  *  Array           →  list | None
"""

from __future__ import annotations
from typing import Any


class RESPError(Exception):
    """Wraps a Redis protocol-level error message."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ProtocolError(Exception):
    """Raised when the incoming byte stream violates RESP framing."""


class RESPParser:
    """
    Incremental RESP parser backed by a byte buffer.

    Usage::

        parser = RESPParser()
        parser.feed(data)          # append raw bytes
        for value in parser:       # iterate fully-parsed values
            handle(value)
    """

    CRLF = b"\r\n"

    def __init__(self) -> None:
        self._buf = bytearray()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def feed(self, data: bytes) -> None:
        """Append raw bytes to the internal buffer."""
        self._buf.extend(data)

    def __iter__(self):
        return self

    def __next__(self) -> Any:
        if not self._buf:
            raise StopIteration
        value, consumed = self._parse(0)
        if consumed == 0:
            raise StopIteration
        del self._buf[:consumed]
        return value

    # ------------------------------------------------------------------
    # Parsing internals
    # ------------------------------------------------------------------

    def _parse(self, offset: int) -> tuple[Any, int]:
        """
        Try to parse one RESP value starting at *offset*.

        Returns (value, bytes_consumed).  bytes_consumed == 0 means
        not enough data has arrived yet (caller should wait for more).
        """
        buf = self._buf
        if offset >= len(buf):
            return None, 0

        type_byte = chr(buf[offset])
        offset += 1

        if type_byte == "+":
            return self._parse_simple_string(offset)
        if type_byte == "-":
            return self._parse_error(offset)
        if type_byte == ":":
            return self._parse_integer(offset)
        if type_byte == "$":
            return self._parse_bulk_string(offset)
        if type_byte == "*":
            return self._parse_array(offset)

        raise ProtocolError(f"Unknown RESP type byte: {type_byte!r}")

    # ---- individual type parsers ----------------------------------------

    def _read_line(self, offset: int) -> tuple[bytes, int]:
        """Return (line_without_CRLF, new_offset) or ('', 0) if incomplete."""
        end = self._buf.find(self.CRLF, offset)
        if end == -1:
            return b"", 0
        line = bytes(self._buf[offset:end])
        return line, end + 2  # skip past \r\n

    def _parse_simple_string(self, offset: int) -> tuple[str, int]:
        line, new_off = self._read_line(offset)
        if not new_off:
            return None, 0
        return line.decode("utf-8"), new_off

    def _parse_error(self, offset: int) -> tuple[RESPError, int]:
        line, new_off = self._read_line(offset)
        if not new_off:
            return None, 0
        return RESPError(line.decode("utf-8")), new_off

    def _parse_integer(self, offset: int) -> tuple[int, int]:
        line, new_off = self._read_line(offset)
        if not new_off:
            return None, 0
        return int(line), new_off

    def _parse_bulk_string(self, offset: int) -> tuple[bytes | None, int]:
        line, new_off = self._read_line(offset)
        if not new_off:
            return None, 0
        length = int(line)
        if length == -1:
            return None, new_off  # RESP null bulk string

        end = new_off + length
        if end + 2 > len(self._buf):  # +2 for trailing CRLF
            return None, 0
        data = bytes(self._buf[new_off:end])
        return data, end + 2

    def _parse_array(self, offset: int) -> tuple[list | None, int]:
        line, new_off = self._read_line(offset)
        if not new_off:
            return None, 0
        count = int(line)
        if count == -1:
            return None, new_off  # RESP null array

        items: list = []
        cur = new_off
        for _ in range(count):
            value, consumed = self._parse(cur)
            if consumed == 0:
                return None, 0
            items.append(value)
            cur = consumed
        return items, cur

    # ------------------------------------------------------------------
    # Class-level helpers
    # ------------------------------------------------------------------

    @classmethod
    def parse_one(cls, data: bytes) -> Any:
        """Parse exactly one RESP value from *data* and return it."""
        p = cls()
        p.feed(data)
        return next(p)
