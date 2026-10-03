"""TCP interface: one command line in, one JSON line out, one thread per client."""

import json
import sys
import threading

from state import ChatError


def serve_tcp(listener, state):
    """Accept clients forever and give each one its own thread."""
    while True:
        conn, address = listener.accept()
        threading.Thread(target=handle_client, args=(conn, address, state), daemon=True).start()


def handle_client(conn, address, state):
    print(f"TCP client connected from {address[0]}:{address[1]}", file=sys.stderr)
    session = {"user": None}  # who is logged in on this connection
    try:
        with conn, conn.makefile("r", encoding="utf-8", errors="replace") as lines:
            # The loop ends when the client quits, closes the socket, or is killed.
            for line in lines:
                response = run_command(line, state, session)
                conn.sendall((json.dumps(response) + "\n").encode())
                if response.get("operation") == "quit":
                    break
    except OSError:
        pass  # connection reset: treated like any other disconnect
    finally:
        # Failure detection: however the client left, log it out of every channel.
        if session["user"]:
            state.logout(session["user"])
        print(f"TCP client disconnected: {session['user'] or '(not logged in)'}", file=sys.stderr)


def run_command(line, state, session):
    """Run one command and return its JSON response, success or error."""
    # strip() drops the "\n"; maxsplit=2 keeps "SEND #cs249 hello there" text in one piece.
    words = line.strip().split(maxsplit=2)
    try:
        return execute(words, state, session)
    except ChatError as error:
        return error.to_json()
    except (IndexError, ValueError):
        # A missing argument, or a HISTORY limit that is not a number.
        return ChatError(400, "BAD_REQUEST", "Malformed command.").to_json()
    except Exception:
        # Anything unexpected: answer with an error and keep the connection open.
        return ChatError(500, "SERVER_ERROR", "Unexpected server error.").to_json()


def ok(operation, **fields):
    return {"status": "ok", "operation": operation, **fields}
