"""
Integration tests for the command dispatcher.

These tests exercise the full path: raw bytes → parser → registry → encoder.
"""

import pytest
from kvault.store import KVStore
from kvault.commands.registry import CommandRegistry
from kvault.protocol.encoder import RESPError, OK, RESPOk


@pytest.fixture
def store():
    return KVStore()


@pytest.fixture
def reg():
    return CommandRegistry()


def cmd(reg, store, *parts: str):
    """Helper: dispatch a command given as string tokens."""
    raw = [p.encode() for p in parts]
    return reg.dispatch(store, raw)


class TestServerCommands:
    def test_ping(self, reg, store):
        assert cmd(reg, store, "PING") == "PONG"

    def test_ping_with_message(self, reg, store):
        assert cmd(reg, store, "PING", "hello") == b"hello"

    def test_echo(self, reg, store):
        assert cmd(reg, store, "ECHO", "world") == b"world"

    def test_dbsize(self, reg, store):
        cmd(reg, store, "SET", "k", "v")
        assert cmd(reg, store, "DBSIZE") == 1

    def test_flushdb(self, reg, store):
        cmd(reg, store, "SET", "k", "v")
        cmd(reg, store, "FLUSHDB")
        assert cmd(reg, store, "DBSIZE") == 0

    def test_unknown_command(self, reg, store):
        result = cmd(reg, store, "NOTACOMMAND")
        assert isinstance(result, RESPError)

    def test_empty_command(self, reg, store):
        result = reg.dispatch(store, [])
        assert isinstance(result, RESPError)


class TestStringCommands:
    def test_set_get(self, reg, store):
        cmd(reg, store, "SET", "k", "hello")
        assert cmd(reg, store, "GET", "k") == b"hello"

    def test_get_missing(self, reg, store):
        assert cmd(reg, store, "GET", "nope") is None

    def test_set_nx(self, reg, store):
        assert isinstance(cmd(reg, store, "SET", "k", "first", "NX"), RESPOk)
        assert cmd(reg, store, "SET", "k", "second", "NX") is None

    def test_set_xx(self, reg, store):
        assert cmd(reg, store, "SET", "k", "v", "XX") is None
        cmd(reg, store, "SET", "k", "v")
        assert isinstance(cmd(reg, store, "SET", "k", "new", "XX"), RESPOk)

    def test_set_ex_and_ttl(self, reg, store):
        cmd(reg, store, "SET", "k", "v", "EX", "10")
        ttl = cmd(reg, store, "TTL", "k")
        assert 8 <= ttl <= 10

    def test_mset_mget(self, reg, store):
        cmd(reg, store, "MSET", "a", "1", "b", "2")
        result = cmd(reg, store, "MGET", "a", "b", "c")
        assert result == [b"1", b"2", None]

    def test_incr_decr(self, reg, store):
        cmd(reg, store, "SET", "n", "10")
        assert cmd(reg, store, "INCR", "n") == 11
        assert cmd(reg, store, "DECR", "n") == 10
        assert cmd(reg, store, "INCRBY", "n", "5") == 15
        assert cmd(reg, store, "DECRBY", "n", "3") == 12

    def test_append_strlen(self, reg, store):
        cmd(reg, store, "SET", "k", "Hello")
        cmd(reg, store, "APPEND", "k", " World")
        assert cmd(reg, store, "STRLEN", "k") == 11

    def test_setnx(self, reg, store):
        assert cmd(reg, store, "SETNX", "k", "v") == 1
        assert cmd(reg, store, "SETNX", "k", "v2") == 0

    def test_setex(self, reg, store):
        cmd(reg, store, "SETEX", "k", "5", "val")
        ttl = cmd(reg, store, "TTL", "k")
        assert 3 <= ttl <= 5

    def test_getrange(self, reg, store):
        cmd(reg, store, "SET", "k", "Hello World")
        assert cmd(reg, store, "GETRANGE", "k", "0", "4") == b"Hello"


class TestKeyCommands:
    def test_del(self, reg, store):
        cmd(reg, store, "SET", "a", "1")
        cmd(reg, store, "SET", "b", "2")
        assert cmd(reg, store, "DEL", "a", "b", "c") == 2

    def test_exists(self, reg, store):
        cmd(reg, store, "SET", "k", "v")
        assert cmd(reg, store, "EXISTS", "k") == 1
        assert cmd(reg, store, "EXISTS", "missing") == 0

    def test_type(self, reg, store):
        cmd(reg, store, "SET", "s", "v")
        assert cmd(reg, store, "TYPE", "s") == "string"
        cmd(reg, store, "LPUSH", "l", "v")
        assert cmd(reg, store, "TYPE", "l") == "list"
        cmd(reg, store, "HSET", "h", "f", "v")
        assert cmd(reg, store, "TYPE", "h") == "hash"

    def test_expire_ttl_persist(self, reg, store):
        cmd(reg, store, "SET", "k", "v")
        cmd(reg, store, "EXPIRE", "k", "10")
        assert cmd(reg, store, "TTL", "k") > 0
        cmd(reg, store, "PERSIST", "k")
        assert cmd(reg, store, "TTL", "k") == -1

    def test_keys_pattern(self, reg, store):
        cmd(reg, store, "SET", "user:1", "Alice")
        cmd(reg, store, "SET", "user:2", "Bob")
        cmd(reg, store, "SET", "post:1", "Hello")
        result = cmd(reg, store, "KEYS", "user:*")
        assert set(result) == {"user:1", "user:2"}


class TestListCommands:
    def test_lpush_rpush_lrange(self, reg, store):
        cmd(reg, store, "RPUSH", "l", "a", "b", "c")
        assert cmd(reg, store, "LRANGE", "l", "0", "-1") == [b"a", b"b", b"c"]

    def test_lpop_rpop(self, reg, store):
        cmd(reg, store, "RPUSH", "l", "x", "y", "z")
        assert cmd(reg, store, "LPOP", "l") == b"x"
        assert cmd(reg, store, "RPOP", "l") == b"z"

    def test_llen(self, reg, store):
        cmd(reg, store, "RPUSH", "l", "a", "b")
        assert cmd(reg, store, "LLEN", "l") == 2

    def test_lindex(self, reg, store):
        cmd(reg, store, "RPUSH", "l", "a", "b", "c")
        assert cmd(reg, store, "LINDEX", "l", "0") == b"a"
        assert cmd(reg, store, "LINDEX", "l", "-1") == b"c"

    def test_lset(self, reg, store):
        cmd(reg, store, "RPUSH", "l", "a", "b")
        cmd(reg, store, "LSET", "l", "1", "B")
        assert cmd(reg, store, "LRANGE", "l", "0", "-1") == [b"a", b"B"]

    def test_linsert_before(self, reg, store):
        cmd(reg, store, "RPUSH", "l", "a", "c")
        cmd(reg, store, "LINSERT", "l", "BEFORE", "c", "b")
        assert cmd(reg, store, "LRANGE", "l", "0", "-1") == [b"a", b"b", b"c"]


class TestHashCommands:
    def test_hset_hget(self, reg, store):
        cmd(reg, store, "HSET", "h", "name", "Alice")
        assert cmd(reg, store, "HGET", "h", "name") == b"Alice"

    def test_hmset_hmget(self, reg, store):
        cmd(reg, store, "HMSET", "h", "a", "1", "b", "2")
        assert cmd(reg, store, "HMGET", "h", "a", "c", "b") == [b"1", None, b"2"]

    def test_hgetall(self, reg, store):
        cmd(reg, store, "HSET", "h", "x", "10", "y", "20")
        result = cmd(reg, store, "HGETALL", "h")
        # Alternating field/value list
        pairs = {result[i].decode(): result[i + 1] for i in range(0, len(result), 2)}
        assert pairs == {"x": b"10", "y": b"20"}

    def test_hdel_hexists(self, reg, store):
        cmd(reg, store, "HSET", "h", "f", "v")
        assert cmd(reg, store, "HEXISTS", "h", "f") == 1
        cmd(reg, store, "HDEL", "h", "f")
        assert cmd(reg, store, "HEXISTS", "h", "f") == 0

    def test_hlen_hkeys_hvals(self, reg, store):
        cmd(reg, store, "HSET", "h", "a", "1", "b", "2")
        assert cmd(reg, store, "HLEN", "h") == 2
        assert set(cmd(reg, store, "HKEYS", "h")) == {b"a", b"b"}
        assert set(cmd(reg, store, "HVALS", "h")) == {b"1", b"2"}

    def test_hincrby(self, reg, store):
        cmd(reg, store, "HSET", "h", "score", "5")
        assert cmd(reg, store, "HINCRBY", "h", "score", "3") == 8
