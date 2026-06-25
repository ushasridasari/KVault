"""
KVault CLI client — a minimal interactive Redis-compatible client.

Usage:
    python client.py [--host HOST] [--port PORT]

Supports:
  - Multi-bulk RESP command encoding
  - Inline command parsing (type commands naturally)
  - Pipelining via semicolons: SET foo bar; GET foo
  - Ctrl-D / Ctrl-C to exit
"""

from __future__ import annotations

import argparse
import socket
import sys


CRLF = b"\r\n"


def encode_command(parts: list[str]) -> bytes:
    """Encode a command as a RESP array of bulk strings."""
    buf = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        encoded = part.encode("utf-8")
        buf.append(f"${len(encoded)}\r\n".encode())
        buf.append(encoded)
        buf.append(CRLF)
    return b"".join(buf)


def read_response(sock: socket.socket) -> str:
    """Read one complete RESP response and return a human-readable string."""
    buf = b""

    def recv_until_crlf() -> bytes:
        nonlocal buf
        while CRLF not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("Server closed connection")
            buf += chunk
        line, buf = buf.split(CRLF, 1)
        return line

    def parse() -> str:
        line = recv_until_crlf()
        prefix = chr(line[0])
        data = line[1:].decode("utf-8", errors="replace")

        if prefix == "+":
            return data
        if prefix == "-":
            return f"(error) {data}"
        if prefix == ":":
            return f"(integer) {data}"
        if prefix == "$":
            length = int(data)
            if length == -1:
                return "(nil)"
            nonlocal buf
            while len(buf) < length + 2:
                buf += sock.recv(4096)
            content = buf[:length]
            buf = buf[length + 2:]
            return f'"{content.decode("utf-8", errors="replace")}"'
        if prefix == "*":
            count = int(data)
            if count == -1:
                return "(empty array)"
            items = []
            for i in range(count):
                items.append(f"{i + 1}) {parse()}")
            return "\n".join(items)
        return f"(unknown prefix {prefix!r}) {data}"

    return parse()


def repl(host: str, port: int) -> None:
    try:
        sock = socket.create_connection((host, port), timeout=5)
    except ConnectionRefusedError:
        print(f"Could not connect to KVault at {host}:{port}")
        sys.exit(1)

    print(f"Connected to KVault {host}:{port}. Type 'quit' to exit.")

    try:
        while True:
            try:
                line = input(f"{host}:{port}> ").strip()
            except EOFError:
                break
            if not line:
                continue
            if line.lower() in ("quit", "exit"):
                break

            # Support semicolon-separated pipelining
            commands = [c.strip() for c in line.split(";") if c.strip()]
            for cmd_str in commands:
                parts = cmd_str.split()
                if not parts:
                    continue
                sock.sendall(encode_command(parts))
                try:
                    print(read_response(sock))
                except ConnectionError as e:
                    print(f"(error) {e}")
                    return
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        print("\nBye!")


def main() -> None:
    parser = argparse.ArgumentParser(description="KVault CLI client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=6399)
    args = parser.parse_args()
    repl(args.host, args.port)


if __name__ == "__main__":
    main()
