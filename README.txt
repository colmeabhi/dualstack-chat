MINI DISCORD NETWORK SERVICE
============================

Student: Abhishek Ahirrao


DESIGN
------

Mini Discord is one Python process with two interfaces over one shared state
object:

  state.py     ChatState: all users, channels, memberships, and messages,
               guarded by a single lock
  http_api.py  HTTP interface; matches the URL path, calls ChatState,
               returns JSON
  tcp_api.py   raw socket interface; one thread per connected TCP client
  server.py    binds both ports and starts both interfaces

Because both interfaces call methods on the same ChatState object in the same
process, data created through one interface is immediately visible through the
other. Each TCP client and each HTTP request runs in its own thread, so a slow
or failed client never blocks the others.

Failure detection lives in a finally block in handle_client (tcp_api.py). When
a client socket reaches end of stream, that user is logged out and removed
from every channel. QUIT, Ctrl-D, and a killed client process all clean up
through the same code path.


DEPENDENCIES
------------

None. Mini Discord uses only the Python standard library.
Python 3.10 or newer is required. There is no install step.


START THE SERVER
----------------

    ./run.sh --host 127.0.0.1 --tcp-port 9000 --http-port 8080

No interactive input is required. Stop with Ctrl-C.

Health check:

    curl http://127.0.0.1:8080/health
    {"status":"ok"}


RUN THE TCP CLIENT
------------------

    python3 client.py --host 127.0.0.1 --port 9000

Commands: REGISTER, LOGIN, JOIN, LEAVE, SEND, LIST CHANNELS,
LIST USERS <channel>, HISTORY <channel> [limit], LOGOUT, QUIT.


PROTOCOL DECISIONS
------------------

* A channel is created by the first join, because the assignment defines no
  separate create-channel operation. Joining twice is idempotent.
* REGISTER creates an account; LOGIN starts the session on that connection.
* JOIN, LEAVE, and SEND require a TCP login. LIST and HISTORY do not, matching
  the public HTTP GET endpoints.
* One username may be logged in on only one TCP connection at a time; a second
  LOGIN returns CONFLICT.
* Message IDs are global, start at 1, and are assigned while the state lock is
  held. Concurrent senders are ordered by whichever thread acquires the lock
  first and can never receive the same ID.
* HISTORY returns the newest requested messages, oldest to newest.
* User, channel, and member lists are sorted.
* HTTP identity comes from the X-User header.
* Every response is JSON, including errors, which use
  {"status","code","message"}. TCP responses are one JSON object per line.
* A TCP disconnect clears that username's memberships everywhere, including a
  membership originally created over HTTP, because the assignment asks for
  removal from all active channel memberships.
* Failure detection relies on socket end of stream, which covers a closed
  client, a killed process, and a closed terminal. A silently dropped network
  link would need TCP keepalives, which PA1 does not require.
* State is in memory and is lost when the server restarts.


TESTING
-------

Testing is manual, following the assignment's demonstration sequence. Start
the server, then in other terminals:

    curl http://127.0.0.1:8080/health
    curl -X POST http://127.0.0.1:8080/users -d '{"username":"alice"}'
    curl -X POST http://127.0.0.1:8080/channels/%23cs249/members -H "X-User: alice"
    curl -X POST http://127.0.0.1:8080/channels/%23cs249/messages \
         -H "X-User: alice" -d '{"text":"Hello from Alice"}'
    curl http://127.0.0.1:8080/channels/%23cs249/messages

    python3 client.py --host 127.0.0.1 --port 9000
      REGISTER charlie / LOGIN charlie / JOIN #cs249 / HISTORY #cs249 20

To check failure detection, close the TCP client without QUIT and run
curl http://127.0.0.1:8080/channels/%23cs249/users; charlie is gone.


FILES
-----

server.py              Startup: binds both ports, starts both interfaces
state.py               ChatState, the shared data and its lock
http_api.py            HTTP interface
tcp_api.py             TCP interface
client.py              Command-line TCP client
run.sh                 Server startup script
requirements.txt       Notes that there are no dependencies
