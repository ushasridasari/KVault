"""Entry point for the KVault server."""

from __future__ import annotations
import argparse
from kvault.server import run_server


def main() -> None:
    parser = argparse.ArgumentParser(
        description="KVault — Redis-compatible in-memory key-value store"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=6399, help="Bind port")
    parser.add_argument("--rdb", default="kvault_dump.rdb", help="Snapshot file path")
    parser.add_argument(
        "--save-interval",
        type=int,
        default=300,
        help="Auto-save interval in seconds (0 to disable)",
    )
    parser.add_argument(
        "--loglevel",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()
    run_server(
        host=args.host,
        port=args.port,
        rdb_path=args.rdb,
        auto_save=args.save_interval,
        loglevel=args.loglevel,
    )


if __name__ == "__main__":
    main()
