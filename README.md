# KVault

A lightweight in-memory key-value store built from scratch in Python, with its own custom wire protocol, data types, TTL expiry, and persistence.

---

## What It Does

- Clients connect over TCP and send commands like `SET name Alice` / `GET name`
- Data is stored in RAM for fast access
- Keys can auto-expire after a set time (TTL)
- Data is saved to disk periodically so it survives a restart

---

## Features

- **Custom wire protocol** — binary-framed parser written from scratch
- **3 data types** — Strings, Lists, Hashes
- **55+ commands** — SET, GET, EXPIRE, TTL, LPUSH, HSET, and more
- **TTL / expiry** — keys auto-delete after their deadline
- **Persistence** — snapshots saved to disk (foreground + background)
- **Async server** — handles many clients concurrently using `asyncio`
- **110 tests** — covering protocol, store, and command layers

---

## Project Structure

```
kvault/
├── kvault/
│   ├── protocol/       # Wire protocol parser & encoder
│   ├── commands/       # All command handlers (strings, lists, hashes, keys)
│   ├── persistence/    # Snapshot save & load
│   ├── store.py        # In-memory data store with TTL
│   └── server.py       # Async TCP server
├── tests/              # 110 unit & integration tests
├── client.py           # Interactive CLI client
└── main.py             # Server entry point
```

---

## Quickstart

**1. Start the server**
```bash
python main.py
# Listening on 127.0.0.1:6399
```

**2. Connect with the built-in client**
```bash
python client.py
```

**3. Try some commands**
```
> SET user Alice
"OK"
> GET user
"Alice"
> EXPIRE user 60
(integer) 1
> TTL user
(integer) 59
> LPUSH colors red green blue
(integer) 3
> LRANGE colors 0 -1
1) "blue"
2) "green"
3) "red"
```

**4. Run tests**
```bash
pip install pytest
python -m pytest tests/ -v
# 110 passed
```

---

## Server Options

| Flag | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `6399` | Bind port |
| `--rdb` | `kvault_dump.rdb` | Snapshot file |
| `--save-interval` | `300` | Auto-save every N seconds |
| `--loglevel` | `INFO` | Log verbosity |

---

## Supported Commands

| Type | Commands |
|---|---|
| **String** | `GET` `SET` `MGET` `MSET` `INCR` `DECR` `APPEND` `STRLEN` `SETNX` `SETEX` |
| **List** | `LPUSH` `RPUSH` `LPOP` `RPOP` `LRANGE` `LLEN` `LINDEX` `LSET` `LINSERT` |
| **Hash** | `HSET` `HGET` `HMGET` `HGETALL` `HDEL` `HEXISTS` `HLEN` `HKEYS` `HVALS` `HINCRBY` |
| **Key** | `DEL` `EXISTS` `TYPE` `KEYS` `RENAME` `EXPIRE` `TTL` `PTTL` `PERSIST` |
| **Server** | `PING` `ECHO` `DBSIZE` `FLUSHDB` |

---

## How It Works

```
Client (TCP)
    │  custom wire protocol
    ▼
AsyncIO Server
    │
    ├── Protocol Parser   →  decodes raw bytes into commands
    ├── Command Registry  →  routes to the right handler
    ├── KV Store          →  reads/writes data (thread-safe, TTL-aware)
    └── RDB Snapshot      →  saves store to disk in background
```

---

## Tech Stack

- **Language:** Python 3.10+
- **Concurrency:** `asyncio`
- **Testing:** `pytest`
- **Persistence:** gzip-compressed JSON snapshot
- **No external dependencies** for the core server
