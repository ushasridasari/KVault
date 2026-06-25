"""
Async TCP server — asyncio-based, handles many concurrent clients.

Architecture:
  - One asyncio event loop per process.
  - Each client connection runs in its own coroutine.
  - The KVStore and CommandRegistry are shared across all connections.
  - RDB persistence is managed separately via the RDBSnapshot helper.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

from kvault.store import KVStore
from kvault.commands.registry import CommandRegistry
from kvault.protocol.parser import RESPParser, RESPError, ProtocolError
from kvault.protocol.encoder import RESPEncoder
from kvault.persistence.rdb import RDBSnapshot

log = logging.getLogger(__name__)


class ClientHandler:
    """Handles one connected client: parse → dispatch → encode → send."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        store: KVStore,
        registry: CommandRegistry,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._store = store
        self._registry = registry
        self._parser = RESPParser()
        peer = writer.get_extra_info("peername")
        self._peer = f"{peer[0]}:{peer[1]}" if peer else "?"

    async def run(self) -> None:
        log.info("Client connected: %s", self._peer)
        try:
            while True:
                chunk = await self._reader.read(4096)
                if not chunk:
                    break
                self._parser.feed(chunk)
                for command in self._parser:
                    await self._handle_command(command)
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        except ProtocolError as e:
            log.warning("Protocol error from %s: %s", self._peer, e)
            self._writer.write(RESPEncoder.error(f"ERR Protocol error: {e}"))
        finally:
            log.info("Client disconnected: %s", self._peer)
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass

    async def _handle_command(self, command) -> None:
        if not isinstance(command, list):
            self._writer.write(RESPEncoder.error("ERR expected array command"))
            await self._writer.drain()
            return

        result = self._registry.dispatch(self._store, command)
        self._writer.write(RESPEncoder.encode(result))
        await self._writer.drain()


class KVaultServer:
    """Top-level server: binds the socket, manages lifecycle."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6399,
        rdb_path: str = "kvault_dump.rdb",
        auto_save_interval: int = 300,
    ) -> None:
        self.host = host
        self.port = port
        self._store = KVStore()
        self._registry = CommandRegistry()
        self._rdb = RDBSnapshot(self._store, rdb_path)
        self._auto_save_interval = auto_save_interval
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        # Load persisted data
        self._rdb.load()
        self._rdb.start_auto_save(self._auto_save_interval)

        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        log.info("KVault listening on %s:%d", self.host, self.port)

        # Graceful shutdown on SIGINT / SIGTERM
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._shutdown)
            except NotImplementedError:
                # Windows
                pass

        async with self._server:
            await self._server.serve_forever()

    def _shutdown(self) -> None:
        log.info("Shutdown signal received — saving snapshot…")
        self._rdb.save()
        self._rdb.stop_auto_save()
        if self._server:
            self._server.close()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        handler = ClientHandler(reader, writer, self._store, self._registry)
        await handler.run()


def run_server(
    host: str = "127.0.0.1",
    port: int = 6399,
    rdb_path: str = "kvault_dump.rdb",
    auto_save: int = 300,
    loglevel: str = "INFO",
) -> None:
    logging.basicConfig(
        level=getattr(logging, loglevel.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    server = KVaultServer(host, port, rdb_path, auto_save)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        pass
