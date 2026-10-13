#!/usr/bin/env python3
"""Mini Discord: one process that serves the same chat data over HTTP and TCP.

    state.py     the shared data (users, channels, messages) and its lock
    http_api.py  the HTTP interface
    tcp_api.py   the raw TCP interface
"""

import argparse
import socket
import sys
import threading

from http_api import ChatHTTPServer
from state import ChatState
from tcp_api import serve_tcp


def main():
    parser = argparse.ArgumentParser(description="Run the Mini Discord server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--tcp-port", type=int, default=9000)
    parser.add_argument("--http-port", type=int, default=8080)
    args = parser.parse_args()

    state = ChatState()  # the one object both interfaces share

    # Bind both ports before starting, so a busy port stops the server right away.
    tcp_listener = socket.create_server((args.host, args.tcp_port))
    http_server = ChatHTTPServer((args.host, args.http_port), state)

    threading.Thread(target=serve_tcp, args=(tcp_listener, state), daemon=True).start()
    print(f"TCP interface listening on {args.host}:{args.tcp_port}", file=sys.stderr)
    print(f"HTTP interface listening on {args.host}:{args.http_port}", file=sys.stderr)

    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
