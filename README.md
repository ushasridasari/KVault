# KVault

A Redis-compatible in-memory key-value store built from scratch in Python.

KVault implements the **RESP v2 wire protocol** so any standard Redis client
(`redis-cli`, `redis-py`, `ioredis`, etc.) can connect to it without modification.

---

## Features

| Layer | What's implemented |
|---|---|
| **Protocol** | Full RESP v2 parser + encoder (simple strings, errors, integers, bulk strings, arrays, null variants) |
| **Data types** | Strings · Lists (via `deque`) · Hashes |
| **String commands** | `GET` `SET` `GETSET` `MGET` `MSET` `MSETNX` `SETNX` `SETEX` `PSETEX` `INCR` `DECR` `INCRBY` `DECRBY` `INCRBYFLOAT` `APPEND` `STRLEN` `GETRANGE` |
| **Key commands** | `DEL` `EXISTS` `TYPE` `KEYS` `RENAME` `EXPIRE` `PEXPIRE` `EXPIREAT` `PERSIST` `TTL` `PTTL` |
| **List commands** | `LPUSH` `RPUSH` `LPUSHX` `RPUSHX` `LPOP` `RPOP` `LRANGE` `LLEN` `LINDEX` `LSET` `LINSERT` |
| **Hash commands** | `HSET` `HGET` `HMGET` `HMSET` `HGETALL` `HDEL` `HEXISTS` `HLEN` `HKEYS` `HVALS` `HINCRBY` |
| **Server commands** | `PING` `ECHO` `DBSIZE` `FLUSHDB` `COMMAND` |
| **TTL / expiry** | Per-key expiry with lazy eviction (checked on access) |
| **Persistence** | Gzip-compressed JSON snapshot (foreground `SAVE` + background `BGSAVE`) with configurable auto-save |
| **Concurrency** | `asyncio`-based server — handles many concurrent clients on one thread |
| **Thread safety** | `RLock`-protected store for safe use from background persistence threads |

---

## Project Structure

```
kvault/
├── kvault/
│   ├── protocol/
│   │   ├── parser.py        # Incremental RESP v2 parser
│   │   └── encoder.py       # RESP v2 encoder
│   ├── commands/
│   │   ├── registry.py      # Command dispatcher
│   │   ├── strings.py       # String command handlers
│   │   ├── keys.py          # Generic key command handlers
│   │   ├── lists.py         # List command handlers
│   │   ├── hashes.py        # Hash command handlers
│   │   └── server_cmds.py   # PING, ECHO, DBSIZE, FLUSHDB
│   ├── persistence/
│   │   └── rdb.py           # Snapshot save / load
│   ├── store.py             # Thread-safe in-memory KV store
│   └── server.py            # asyncio TCP server
├── tests/
│   ├── test_protocol.py     # 29 RESP parser/encoder tests
│   ├── test_store.py        # 46 store unit tests
│   └── test_commands.py     # 35 command integration tests
├── client.py                # Interactive CLI client
└── main.py                  # Server entry point
```

---

## Quickstart

### 1. Run the server

```bash
python main.py
# KVault listening on 127.0.0.1:6399
```

Options:

```
--host          Bind address          (default: 127.0.0.1)
--port          Bind port             (default: 6399)
--rdb           Snapshot file path    (default: kvault_dump.rdb)
--save-interval Auto-save seconds     (default: 300)
--loglevel      DEBUG/INFO/WARNING    (default: INFO)
```

### 2. Connect with the built-in client

```bash
python client.py
# Connected to KVault 127.0.0.1:6399. Type 'quit' to exit.

127.0.0.1:6399> SET user:1 Alice
"OK"
127.0.0.1:6399> GET user:1
"Alice"
127.0.0.1:6399> EXPIRE user:1 60
(integer) 1
127.0.0.1:6399> TTL user:1
(integer) 59
```

Semicolons pipeline multiple commands on one line:

```
127.0.0.1:6399> SET a 1; SET b 2; MGET a b c
"OK"
"OK"
1) "1"
2) "2"
3) (nil)
```

### 3. Connect with `redis-cli` (standard Redis client)

```bash
redis-cli -p 6399
```

### 4. Run tests

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## Design Notes

### RESP Parser — incremental, zero-copy

`RESPParser` maintains an internal `bytearray` buffer.  Incoming TCP chunks
are `feed()`-ed in; parsed values are consumed by iterating the parser.
The buffer advances only when a full message is available, so partial frames
(common under high load) are handled correctly without copying data.

### Lazy expiry

Expired keys are **not** scanned eagerly.  Instead, every read operation
checks `_expire_if_needed()` and evicts on the first access after the
deadline.  This is the same strategy Redis uses and keeps the hot path fast.

### Thread safety

The `KVStore` is protected by a single `threading.RLock`.  Compound
operations (e.g. `SET NX`, `MSETNX`, `LINSERT`) hold the lock for their
entire duration, ensuring atomicity even when background persistence threads
call `snapshot()` concurrently.

### Persistence

Snapshots are written atomically: a `.tmp` file is written first, then
`Path.replace()` does an atomic rename.  This prevents a crash mid-write
from corrupting the last good snapshot.

---

## Architecture Diagram

```
Client (redis-cli / kvault client.py)
        │  TCP  (RESP wire protocol)
        ▼
┌─────────────────────────────────────┐
│          KVaultServer               │
│   asyncio event loop + StreamReader │
│                                     │
│   ClientHandler (per connection)    │
│   ┌──────────┐   ┌──────────────┐  │
│   │  RESP    │   │   RESP       │  │
│   │  Parser  │──▶│   Encoder    │  │
│   └──────────┘   └──────────────┘  │
│         │                ▲         │
│         ▼                │         │
│   CommandRegistry.dispatch()        │
│         │                │         │
│         ▼                │         │
│      KVStore (strings / lists / hashes + TTL)
│         │                          │
│   RDBSnapshot (background save)    │
└─────────────────────────────────────┘
```

---

## Test Results

```
110 passed in 3.33s
```

- **29** RESP protocol tests (parser + encoder roundtrips)  
- **46** KVStore unit tests (strings, lists, hashes, TTL, snapshot)  
- **35** command integration tests (full dispatch path)

---

## Extending KVault

To add a new command:

1. Write a handler `fn(store: KVStore, args: list[bytes]) -> Any` in the
   appropriate module under `kvault/commands/`.
2. Add it to that module's `COMMANDS` dict.
3. The `CommandRegistry` picks it up automatically — no changes needed there.
