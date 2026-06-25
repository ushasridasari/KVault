"""Tests for KVStore — strings, lists, hashes, TTL, and generic key ops."""

import time
import pytest
from kvault.store import KVStore, WrongTypeError


@pytest.fixture
def store():
    return KVStore()


# ---------------------------------------------------------------------------
# String operations
# ---------------------------------------------------------------------------

class TestStrings:
    def test_set_and_get(self, store):
        store.set("k", b"hello")
        assert store.get("k") == b"hello"

    def test_get_missing(self, store):
        assert store.get("nope") is None

    def test_overwrite(self, store):
        store.set("k", b"a")
        store.set("k", b"b")
        assert store.get("k") == b"b"

    def test_set_nx(self, store):
        assert store.set("k", b"first", nx=True) is True
        assert store.set("k", b"second", nx=True) is False
        assert store.get("k") == b"first"

    def test_set_xx(self, store):
        assert store.set("k", b"val", xx=True) is False
        store.set("k", b"val")
        assert store.set("k", b"new", xx=True) is True

    def test_set_ex(self, store):
        store.set("k", b"v", ex=1)
        assert store.get("k") == b"v"
        time.sleep(1.05)
        assert store.get("k") is None

    def test_incr(self, store):
        store.set("n", b"10")
        assert store.incr("n") == 11

    def test_incr_missing(self, store):
        assert store.incr("x") == 1

    def test_decr(self, store):
        store.set("n", b"5")
        assert store.decr("n") == 4

    def test_incr_non_integer(self, store):
        store.set("k", b"hello")
        with pytest.raises(ValueError):
            store.incr("k")

    def test_mset_mget(self, store):
        store.mset({"a": b"1", "b": b"2"})
        assert store.mget("a", "b", "c") == [b"1", b"2", None]

    def test_append(self, store):
        store.set("k", b"hello")
        length = store.append("k", b" world")
        assert length == 11
        assert store.get("k") == b"hello world"

    def test_strlen(self, store):
        store.set("k", b"abc")
        assert store.strlen("k") == 3
        assert store.strlen("missing") == 0

    def test_getrange(self, store):
        store.set("k", b"Hello World")
        assert store.getrange("k", 0, 4) == b"Hello"
        assert store.getrange("k", -5, -1) == b"World"

    def test_incrbyfloat(self, store):
        store.set("k", b"10.5")
        result = store.incrbyfloat("k", 0.1)
        assert abs(result - 10.6) < 1e-9


# ---------------------------------------------------------------------------
# TTL
# ---------------------------------------------------------------------------

class TestTTL:
    def test_ttl_no_expiry(self, store):
        store.set("k", b"v")
        assert store.ttl("k") == -1

    def test_ttl_missing_key(self, store):
        assert store.ttl("nope") == -2

    def test_ttl_with_expiry(self, store):
        store.set("k", b"v", ex=10)
        ttl = store.ttl("k")
        assert 8 <= ttl <= 10

    def test_expire_then_evict(self, store):
        store.set("k", b"v")
        store.expire("k", 1)
        time.sleep(1.05)
        assert store.get("k") is None

    def test_persist(self, store):
        store.set("k", b"v", ex=10)
        store.persist("k")
        assert store.ttl("k") == -1

    def test_expire_missing(self, store):
        assert store.expire("nope", 5) == 0


# ---------------------------------------------------------------------------
# Generic key ops
# ---------------------------------------------------------------------------

class TestKeys:
    def test_exists(self, store):
        store.set("k", b"v")
        assert store.exists("k") == 1
        assert store.exists("k", "k") == 2  # same key counted twice
        assert store.exists("missing") == 0

    def test_delete(self, store):
        store.set("a", b"1")
        store.set("b", b"2")
        assert store.delete("a", "b", "c") == 2
        assert store.get("a") is None

    def test_keys_pattern(self, store):
        store.set("foo", b"1")
        store.set("foobar", b"2")
        store.set("bar", b"3")
        assert set(store.keys("foo*")) == {"foo", "foobar"}
        assert set(store.keys("*")) == {"foo", "foobar", "bar"}

    def test_key_type(self, store):
        store.set("s", b"v")
        assert store.key_type("s") == "string"
        store.lpush("l", b"v")
        assert store.key_type("l") == "list"
        store.hset("h", {"f": b"v"})
        assert store.key_type("h") == "hash"
        assert store.key_type("none") == "none"

    def test_dbsize(self, store):
        assert store.dbsize() == 0
        store.set("k", b"v")
        assert store.dbsize() == 1

    def test_flushdb(self, store):
        store.set("k", b"v")
        store.flushdb()
        assert store.dbsize() == 0


# ---------------------------------------------------------------------------
# List operations
# ---------------------------------------------------------------------------

class TestLists:
    def test_lpush_rpush_lrange(self, store):
        store.lpush("l", b"b", b"a")  # a is leftmost after two lpush
        store.rpush("l", b"c")
        assert store.lrange("l", 0, -1) == [b"a", b"b", b"c"]

    def test_lpop_rpop(self, store):
        store.rpush("l", b"1", b"2", b"3")
        assert store.lpop("l") == b"1"
        assert store.rpop("l") == b"3"
        assert store.lrange("l", 0, -1) == [b"2"]

    def test_llen(self, store):
        store.rpush("l", b"a", b"b")
        assert store.llen("l") == 2

    def test_lindex(self, store):
        store.rpush("l", b"x", b"y", b"z")
        assert store.lindex("l", 0) == b"x"
        assert store.lindex("l", -1) == b"z"
        assert store.lindex("l", 99) is None

    def test_lset(self, store):
        store.rpush("l", b"a", b"b")
        store.lset("l", 1, b"B")
        assert store.lrange("l", 0, -1) == [b"a", b"B"]

    def test_list_auto_delete_when_empty(self, store):
        store.rpush("l", b"v")
        store.lpop("l")
        assert store.key_type("l") == "none"

    def test_wrong_type_error(self, store):
        store.set("s", b"string")
        with pytest.raises(WrongTypeError):
            store.lpush("s", b"val")


# ---------------------------------------------------------------------------
# Hash operations
# ---------------------------------------------------------------------------

class TestHashes:
    def test_hset_hget(self, store):
        store.hset("h", {"name": b"Alice", "age": b"30"})
        assert store.hget("h", "name") == b"Alice"
        assert store.hget("h", "missing") is None

    def test_hgetall(self, store):
        store.hset("h", {"a": b"1", "b": b"2"})
        result = store.hgetall("h")
        assert result == {"a": b"1", "b": b"2"}

    def test_hdel(self, store):
        store.hset("h", {"a": b"1", "b": b"2"})
        assert store.hdel("h", "a") == 1
        assert store.hget("h", "a") is None

    def test_hexists(self, store):
        store.hset("h", {"f": b"v"})
        assert store.hexists("h", "f") == 1
        assert store.hexists("h", "x") == 0

    def test_hlen(self, store):
        store.hset("h", {"a": b"1", "b": b"2"})
        assert store.hlen("h") == 2

    def test_hkeys_hvals(self, store):
        store.hset("h", {"x": b"10", "y": b"20"})
        assert set(store.hkeys("h")) == {"x", "y"}
        assert set(store.hvals("h")) == {b"10", b"20"}

    def test_hincrby(self, store):
        store.hset("h", {"score": b"5"})
        assert store.hincrby("h", "score", 3) == 8

    def test_hmget(self, store):
        store.hset("h", {"a": b"1", "b": b"2"})
        assert store.hmget("h", "a", "c", "b") == [b"1", None, b"2"]

    def test_hash_auto_delete_when_empty(self, store):
        store.hset("h", {"f": b"v"})
        store.hdel("h", "f")
        assert store.key_type("h") == "none"


# ---------------------------------------------------------------------------
# Snapshot / persistence
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_snapshot_restore_string(self, store):
        store.set("k", b"hello")
        snap = store.snapshot()
        new_store = KVStore()
        new_store.restore_snapshot(snap)
        assert new_store.get("k") == b"hello"

    def test_snapshot_restore_list(self, store):
        store.rpush("l", b"a", b"b")
        snap = store.snapshot()
        new_store = KVStore()
        new_store.restore_snapshot(snap)
        assert new_store.lrange("l", 0, -1) == [b"a", b"b"]

    def test_snapshot_restore_hash(self, store):
        store.hset("h", {"f": b"v"})
        snap = store.snapshot()
        new_store = KVStore()
        new_store.restore_snapshot(snap)
        assert new_store.hget("h", "f") == b"v"

    def test_snapshot_excludes_expired(self, store):
        store.set("alive", b"yes")
        store.set("dead", b"no", ex=1)
        time.sleep(1.05)
        snap = store.snapshot()
        assert "alive" in snap
        assert "dead" not in snap
