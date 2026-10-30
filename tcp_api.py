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


def execute(words, state, session):
    command = words[0].upper() if words else ""
    args = words[1:]

    if command == "REGISTER":
        state.add_user(args[0])
        return ok("register", username=args[0])

    if command == "LOGIN":
        if session["user"]:
            raise ChatError(409, "CONFLICT", "This connection is already logged in.")
        state.login(args[0])
        session["user"] = args[0]
        return ok("login", username=args[0])

    if command == "LOGOUT":
        username = logged_in_user(session)
        state.logout(username)
        session["user"] = None
        return ok("logout", username=username)

    if command == "JOIN":
        username = logged_in_user(session)
        state.join(username, args[0])
        return ok("join", channel=args[0], username=username)

    if command == "LEAVE":
        username = logged_in_user(session)
        state.leave(username, args[0])
        return ok("leave", channel=args[0], username=username)

    if command == "SEND":
        message = state.send(logged_in_user(session), args[0], args[1])
        return ok("send", message_id=message["message_id"])

    if command == "LIST" and args[0].upper() == "CHANNELS":
        return ok("list_channels", channels=state.list_channels())

    if command == "LIST" and args[0].upper() == "USERS":
        return ok("list_users", channel=args[1], users=state.channel_users(args[1]))

    if command == "HISTORY":
        limit = int(args[1]) if len(args) > 1 else 20
        return ok("history", channel=args[0], messages=state.history(args[0], limit))

    if command == "QUIT":
        return ok("quit")

    raise ChatError(400, "BAD_REQUEST", f"Unknown command {command}.")


def logged_in_user(session):
    if session["user"] is None:
        raise ChatError(401, "NOT_AUTHENTICATED", "Log in first.")
    return session["user"]


def ok(operation, **fields):
    return {"status": "ok", "operation": operation, **fields}
