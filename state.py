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

    def join(self, username, channel):
        if not CHANNEL.fullmatch(channel):
            raise ChatError(400, "INVALID_CHANNEL", "Start with # and use only letters, digits, - and _.")
        with self.lock:
            self._check_user(username)
            # The first join creates the channel.
            self.members.setdefault(channel, set()).add(username)
            self.messages.setdefault(channel, [])

    def leave(self, username, channel):
        with self.lock:
            self._check_member(username, channel)
            self.members[channel].remove(username)

    def channel_users(self, channel):
        with self.lock:
            self._check_channel(channel)
            return sorted(self.members[channel])

    def send(self, username, channel, text):
        with self.lock:
            self._check_member(username, channel)
            # Taking the id and storing the message under one lock means two
            # clients sending at the same moment can never get the same id.
            message = {"message_id": self.next_id, "username": username, "text": text}
            self.next_id += 1
            self.messages[channel].append(message)
            return {"message_id": message["message_id"], "channel": channel,
                    "username": username, "text": text}

    def history(self, channel, limit):
        with self.lock:
            self._check_channel(channel)
            return self.messages[channel][-limit:]  # newest `limit`, oldest first

    def login(self, username):
        with self.lock:
            self._check_user(username)
            if username in self.online:
                raise ChatError(409, "CONFLICT", f"{username} is already logged in.")
            self.online.add(username)

    def logout(self, username):
        """Used by LOGOUT, QUIT, and a failed client: leave every channel."""
        with self.lock:
            self.online.discard(username)
            for people in self.members.values():
                people.discard(username)

    # Lookups that raise a ChatError. Call them only while holding the lock.

    def _check_user(self, username):
        if username not in self.users:
            raise ChatError(404, "NOT_FOUND", f"User {username} not found.")

    def _check_channel(self, channel):
        if channel not in self.members:
            raise ChatError(404, "NOT_FOUND", f"Channel {channel} not found.")

    def _check_member(self, username, channel):
        self._check_channel(channel)
        if username not in self.members[channel]:
            raise ChatError(403, "NOT_AUTHENTICATED", f"{username} is not in {channel}.")
