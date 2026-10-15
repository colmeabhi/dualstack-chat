#!/usr/bin/env python3
"""Interactive command-line client for Mini Discord's TCP interface."""

from __future__ import annotations

import argparse
import socket
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Connect to Mini Discord over TCP.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        with socket.create_connection((args.host, args.port)) as sock:
            reader = sock.makefile("r", encoding="utf-8", newline="\n")
            print(f"Connected to Mini Discord at {args.host}:{args.port}")
            print("Type a command, or press Ctrl-D to close the client unexpectedly.")

            while True:
                try:
                    command = input("> ")
                except EOFError:
                    print()
                    break
                except KeyboardInterrupt:
                    print("\nConnection closed without QUIT.")
                    break

                sock.sendall((command + "\n").encode("utf-8"))
                response = reader.readline()
                if not response:
                    print("The server closed the connection.", file=sys.stderr)
                    return 1
                print(response.rstrip("\n"))
                if command.strip().upper() == "QUIT":
                    break
    except OSError as error:
        print(f"Could not connect to Mini Discord: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
