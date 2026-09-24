"""All Mini Discord data, shared by the HTTP and TCP interfaces.

Many threads call these methods at the same time, so every method holds
the lock while it reads or changes the data.
"""

import re
import threading

USERNAME = re.compile(r"[A-Za-z0-9_-]+")   # letters, digits, hyphens, underscores
CHANNEL = re.compile(r"#[A-Za-z0-9_-]+")   # same, after a leading #


class ChatError(Exception):
    """An error the client should receive as a JSON response."""

    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status  # HTTP status code (TCP ignores it)
        self.code = code
        self.message = message

    def to_json(self):
        return {"status": "error", "code": self.code, "message": self.message}


class ChatState:
    def __init__(self):
        self.lock = threading.Lock()
        self.users = set()     # every registered username
        self.online = set()    # usernames logged in over TCP
        self.members = {}      # channel -> set of usernames
        self.messages = {}     # channel -> list of messages, oldest first
        self.next_id = 1       # next message id, shared by all channels

    def add_user(self, username):
        # isinstance: a JSON body could send a number, e.g. {"username": 5}.
        if not isinstance(username, str) or not USERNAME.fullmatch(username):
            raise ChatError(400, "INVALID_USERNAME", "Use only letters, digits, - and _.")
        with self.lock:
            if username in self.users:
                raise ChatError(409, "CONFLICT", f"User {username} already exists.")
            self.users.add(username)

    def list_users(self):
        with self.lock:
            return sorted(self.users)

    def list_channels(self):
        with self.lock:
            return sorted(self.members)

