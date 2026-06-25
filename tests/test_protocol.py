"""Tests for RESP parser and encoder."""

import pytest
from kvault.protocol.parser import RESPParser, RESPError, ProtocolError
from kvault.protocol.encoder import RESPEncoder, OK, RESPOk


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class TestRESPParser:
    def _parse(self, data: bytes):
        return RESPParser.parse_one(data)

    def test_simple_string(self):
        assert self._parse(b"+OK\r\n") == "OK"

    def test_simple_string_pong(self):
        assert self._parse(b"+PONG\r\n") == "PONG"

    def test_error(self):
        result = self._parse(b"-ERR something went wrong\r\n")
        assert isinstance(result, RESPError)
        assert "something went wrong" in result.message

    def test_integer(self):
        assert self._parse(b":42\r\n") == 42

    def test_negative_integer(self):
        assert self._parse(b":-7\r\n") == -7

    def test_bulk_string(self):
        assert self._parse(b"$5\r\nhello\r\n") == b"hello"

    def test_bulk_string_empty(self):
        assert self._parse(b"$0\r\n\r\n") == b""

    def test_null_bulk_string(self):
        assert self._parse(b"$-1\r\n") is None

    def test_array(self):
        assert self._parse(b"*3\r\n+a\r\n:1\r\n$3\r\nfoo\r\n") == ["a", 1, b"foo"]

    def test_null_array(self):
        assert self._parse(b"*-1\r\n") is None

    def test_empty_array(self):
        assert self._parse(b"*0\r\n") == []

    def test_nested_array(self):
        data = b"*2\r\n*2\r\n:1\r\n:2\r\n*1\r\n$3\r\nfoo\r\n"
        assert self._parse(data) == [[1, 2], [b"foo"]]

    def test_incremental_feed(self):
        p = RESPParser()
        p.feed(b"+OK")
        assert list(p) == []
        p.feed(b"\r\n")
        assert list(p) == ["OK"]

    def test_multiple_in_buffer(self):
        p = RESPParser()
        p.feed(b"+OK\r\n+PONG\r\n")
        assert list(p) == ["OK", "PONG"]

    def test_unknown_type_raises(self):
        with pytest.raises(ProtocolError):
            RESPParser.parse_one(b"!bad\r\n")


# ---------------------------------------------------------------------------
# Encoder
# ---------------------------------------------------------------------------

class TestRESPEncoder:
    def test_none(self):
        assert RESPEncoder.encode(None) == b"$-1\r\n"

    def test_ok(self):
        assert RESPEncoder.encode(OK) == b"+OK\r\n"

    def test_integer(self):
        assert RESPEncoder.encode(5) == b":5\r\n"

    def test_negative_integer(self):
        assert RESPEncoder.encode(-3) == b":-3\r\n"

    def test_bool_true(self):
        assert RESPEncoder.encode(True) == b":1\r\n"

    def test_bool_false(self):
        assert RESPEncoder.encode(False) == b":0\r\n"

    def test_str(self):
        assert RESPEncoder.encode("hello") == b"$5\r\nhello\r\n"

    def test_bytes(self):
        assert RESPEncoder.encode(b"world") == b"$5\r\nworld\r\n"

    def test_list(self):
        out = RESPEncoder.encode([1, b"foo"])
        assert out == b"*2\r\n:1\r\n$3\r\nfoo\r\n"

    def test_empty_list(self):
        assert RESPEncoder.encode([]) == b"*0\r\n"

    def test_error(self):
        err = RESPError("ERR oops")
        assert RESPEncoder.encode(err) == b"-ERR oops\r\n"

    def test_roundtrip(self):
        """Encode then parse should recover the original value."""
        cases = [
            42,
            b"hello world",
            [1, b"a", b"b"],
        ]
        for value in cases:
            encoded = RESPEncoder.encode(value)
            parsed = RESPParser.parse_one(encoded)
            assert parsed == value, f"Roundtrip failed for {value!r}"

    def test_unknown_type_raises(self):
        with pytest.raises(TypeError):
            RESPEncoder.encode(object())
