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

