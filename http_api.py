"""HTTP interface: turns each request into a ChatState call and answers in JSON."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from state import ChatError


class ChatHTTPServer(ThreadingHTTPServer):
    """Serves each HTTP request on its own thread."""

    daemon_threads = True

    def __init__(self, address, state):
        super().__init__(address, Handler)
        self.state = state


class Handler(BaseHTTPRequestHandler):
    def handle_request(self):
        try:
            status, body = self.route(self.command)  # self.command is "GET", "POST", ...
        except ChatError as error:
            status, body = error.status, error.to_json()
        except ValueError:
            # json.loads() and int() raise ValueError on bad JSON or a bad limit.
            status, body = 400, ChatError(400, "BAD_REQUEST", "Invalid JSON or number.").to_json()
        except Exception:
            # Anything unexpected: answer with an error instead of dropping the request.
            status, body = 500, ChatError(500, "SERVER_ERROR", "Unexpected server error.").to_json()
        self.send_json(status, body)

    # Every HTTP method goes through the same function.
    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = handle_request

    def x_user(self):
        """HTTP has no login, so the X-User header says who is acting."""
        username = self.headers.get("X-User")
        if not username:
            raise ChatError(400, "BAD_REQUEST", "The X-User header is required.")
        return username

    def body_field(self, name):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if name not in body:
            raise ChatError(400, "BAD_REQUEST", f"The field '{name}' is required.")
        return body[name]

    def send_json(self, status, body):
        data = json.dumps(body, separators=(",", ":")).encode()  # compact: {"status":"ok"}
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def allow(method, *methods):
    if method not in methods:
        raise ChatError(405, "METHOD_NOT_ALLOWED", f"Use {' or '.join(methods)}.")
