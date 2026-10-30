# Architectural Decisions

This file explains the main design choices in plain language. The goal is the smallest design that meets the assignment and stays correct when several clients use it at once. Anything the assignment does not ask for (such as username format rules) is left out on purpose.

## Overview

```
                 one Python process (server.py)
   ┌───────────────────────────────────────────────────────┐
   │                                                       │
   │   http_api.py                        tcp_api.py       │
   │   one thread per request             one thread per   │
   │        │                             TCP client       │
   │        │                                  │           │
   │        └──────────►  ChatState  ◄─────────┘           │
   │                      (state.py)                       │
   │                users, channels, messages              │
   │                guarded by one lock                    │
   └───────────────────────────────────────────────────────┘
        ▲ port 8080 (HTTP)               ▲ port 9000 (TCP)
     curl, browsers                  client.py, nc
```

| File | Responsibility |
|---|---|
| `state.py` | The shared data and its lock. Knows nothing about networks. |
| `http_api.py` | Turns HTTP requests into `ChatState` calls and answers in JSON. |
| `tcp_api.py` | Reads one command line, runs it, writes one JSON line. Cleans up when a client leaves. |
| `server.py` | Binds both ports and starts both interfaces with the same `ChatState`. |

## ADR-1: Keep all data in one shared state object

**Status:** Accepted

**Context.** The HTTP and TCP interfaces must see the same users, channels, memberships, and messages. The assignment does not allow a database or message broker.

**Decision.** Create one `ChatState` object in `server.py` and hand it to both interfaces. Every read and write goes through its methods.

Example: if Alice sends a message over HTTP, `HISTORY #cs249` over TCP reads it from the same Python list.

**Consequences.**
- Both interfaces always agree, because there is only one copy of the data.
- Data disappears when the process restarts, which the assignment allows.
- Many threads touch the object at once, so it needs a lock (ADR-2).

## ADR-2: Protect all shared data with one lock

**Status:** Accepted

**Context.** HTTP threads and TCP threads can change the data at nearly the same moment. Without a lock, two messages could get the same ID, or a set could change while another thread is sorting it.

**Decision.** `ChatState` has one `threading.Lock`. Every method does its work inside `with self.lock:`. Taking the next message ID and storing the message happen under the same lock.

Example: Alice and Bob send at the same instant. One thread gets the lock first and takes ID 1; the other waits, then takes ID 2.

**Options considered.**
- No lock: shorter, but wrong under concurrency.
- Many small locks: faster in theory, but harder to reason about and can deadlock.
- One lock: the simplest correct choice for a small in-memory service.

**Consequences.**
- Message IDs are unique and the collections are never seen half-changed.
- A plain `Lock` (not `RLock`) is enough because no locked method calls another locked method. The `_check_*` helpers do not take the lock; they are only called by methods that already hold it.
- Network reads and writes never happen while the lock is held, so a slow client cannot block others.

## ADR-3: Standard library only, both interfaces in one process

**Status:** Accepted

**Context.** The assignment requires raw TCP sockets for the custom protocol, one server process, and allows a standard library or a lightweight framework for HTTP.

**Decision.**
- HTTP: `ThreadingHTTPServer` with one handler. Every HTTP method goes to one function, which uses a `match` statement on the URL path. Each `case` reads like a route, for example `case ["channels", channel, "messages"]`.
- TCP: `socket.create_server` plus an `accept()` loop that starts one thread per client.
- `server.py` binds **both** ports first, then starts the TCP loop on a background thread and runs HTTP on the main thread.

**Consequences.**
- `requirements.txt` lists nothing; `./run.sh` works on a clean Python 3.10+ install.
- If either port is already in use, the server exits immediately with an error instead of running half-started.
- A slow client blocks only its own thread.

## ADR-4: Create a channel when the first user joins it

**Status:** Accepted

**Context.** The assignment asks users to join `#cs249` but defines no create-channel operation.

**Decision.** `POST /channels/{channel}/members` and `JOIN <channel>` create the channel if needed, then add the user. Joining twice is harmless.

**Consequences.**
- Empty channels stay in the channel list after the last user leaves.

## ADR-5: Each TCP connection remembers who is logged in on it

**Status:** Accepted

**Context.** The server must notice when a TCP client disconnects unexpectedly, log that user out, and remove them from every channel.

**Decision.** Each client thread keeps a small `session = {"user": None}` for its own connection. `LOGIN` fills it in; `ChatState.online` records which usernames are logged in anywhere, so one username can be logged in on only one connection at a time. When the read loop ends for any reason (QUIT, Ctrl-D, killed process, reset connection), a `finally` block calls `state.logout(session["user"])`.

`LIST` and `HISTORY` do not require login, matching the public HTTP GET endpoints. `JOIN`, `LEAVE`, and `SEND` do.

Example: Charlie logs in, joins `#cs249`, and closes the terminal. Charlie's thread sees end-of-stream, the `finally` block runs, and Charlie is removed from `#cs249`. Other clients are unaffected.

**Consequences.**
- Cleanup has exactly one owner: the thread that served that connection.
- A second login for the same username gets `CONFLICT`.
- HTTP has no sessions; identity comes from the `X-User` header.

## ADR-6: JSON lines and one error format

**Status:** Accepted

**Context.** TCP is a byte stream with no built-in message boundaries. HTTP errors must also be JSON.

**Decision.**
- Every TCP request is one line ending in `\n`. Every response is one JSON object followed by `\n`.
- Every error, on both interfaces, looks like `{"status":"error","code":"...","message":"..."}`. Expected errors are raised as `ChatError` inside `state.py` and turned into JSON at the edge.
- Malformed input is caught in one place per interface: a missing TCP argument (`IndexError`), a non-numeric limit, or invalid JSON (`ValueError`) all return `BAD_REQUEST`.
- Unknown HTTP paths return `404`; a known path with the wrong method returns `405`.
- Names are checked where they are created: `add_user` rejects usernames outside letters, digits, `-`, `_` (`INVALID_USERNAME`), and `join` rejects channels that do not match `#` plus those characters (`INVALID_CHANNEL`).
- Any other unexpected exception becomes `SERVER_ERROR` (HTTP 500) instead of dropping the request or the TCP connection.

**Consequences.**
- One bad request never stops the server or closes a valid connection.
- Lists are sorted so output is predictable.

## ADR-7: Test by hand with curl and the TCP client

**Status:** Accepted

**Decision.** There is no automated test suite. The server is tested by following the assignment's demonstration sequence: `curl` for every HTTP endpoint, `client.py` for the TCP commands, several clients at once for concurrency, and closing a client without `QUIT` for failure detection. README.txt lists the commands.

**Consequences.** Nothing extra to install or maintain. Every check must be repeated by hand after a change.

## ADR-8: Print server events to stderr

**Status:** Accepted

**Decision.** The server prints only four kinds of lines: the two startup lines, TCP connect, and TCP disconnect. They go to `stderr`, the same stream `http.server` uses for its request log, so all lines appear in order even when output is redirected to a file.

**Consequences.** A failed client is visible the moment it happens:

```
TCP client connected from 127.0.0.1:57981
TCP client disconnected: dave
127.0.0.1 - - [24/Sep/2026 22:51:09] "GET /channels/%23cs249/users HTTP/1.1" 200 -
```
