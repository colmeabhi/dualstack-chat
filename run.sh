#!/usr/bin/env bash
# Starts the Mini Discord server and passes every argument straight through.
#   ./run.sh --host 127.0.0.1 --tcp-port 9000 --http-port 8080
set -euo pipefail

cd "$(dirname "$0")"
exec python3 server.py "$@"
