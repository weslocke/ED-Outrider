"""The notices banner (S5a): what used to be said only in the terminal at start (a journal folder not found, NFS
caching, no password on the network, problems in the config or the spoken lines file, the overlay's address taken)
shown at the top of every page window and the tablet, until it is fixed or dismissed.

One board on the server: `set(key, text, level, action)` / `clear(key)` / `dismiss(id)` / `active()`. A notice's id is
its key and a hash of its text, so a changed message is a new notice and shows again; a dismissal is kept in memory
only (until Outrider restarts: the author's choice), on the server, so every window agrees. At most MAX notices (the
oldest goes). Actions are names the page maps to a button ("open:server", "open:server:journals", "open:log"); one the
page does not know is left out. `warn(key, text)` prints the line as before and posts it.

Importable on its own (no dependency): BOARD exists from the start, before the database opens, so anything run early
can post to it; run() starts a fresh one (`reset()`) and gives it to State.
"""
import hashlib
import sys
import threading

MAX = 20
LEVELS = ("info", "warn", "bad")


def notice_id(key, text):
    return f"{key}:{hashlib.sha1(text.encode('utf-8')).hexdigest()[:10]}"


class Board:
    def __init__(self, on_change=None):
        self.items = {}           # key -> notice, oldest first
        self.dismissed = set()    # ids hidden until a restart (or until that key's text changes)
        self.on_change = on_change
        self.lock = threading.Lock()

    def _changed(self):
        if self.on_change:
            self.on_change()

    def set(self, key, text, level="warn", action=None):
        """Show (or update) the notice for `key`. False when it was already shown as it is."""
        text = " ".join(str(text).split())
        n = {"id": notice_id(key, text), "key": key, "text": text, "level": level if level in LEVELS else "warn",
             "action": action or None}
        with self.lock:
            if self.items.get(key) == n:
                return False   # nothing changed: it keeps its place (review 2026-10-23 S4-B12: it moved to the end)
            old = self.items.pop(key, None)
            if old:
                self.dismissed.discard(old["id"])   # its text changed: that dismissal is over
            self.items[key] = n
            while len(self.items) > MAX:
                gone = self.items.pop(next(iter(self.items)))
                self.dismissed.discard(gone["id"])
        self._changed()
        return True

    def clear(self, key):
        """The problem is gone: the notice too (set again later, it shows again)."""
        with self.lock:
            old = self.items.pop(key, None)
            if old:
                self.dismissed.discard(old["id"])
        if old:
            self._changed()
        return bool(old)

    def dismiss(self, nid):
        """Hide one notice until Outrider restarts or its text changes. False for an id not shown."""
        with self.lock:
            if not any(n["id"] == nid for n in self.items.values()) or nid in self.dismissed:
                return False
            self.dismissed.add(nid)
        self._changed()
        return True

    def active(self):
        """The payload's `notices`: the ones not dismissed, oldest first."""
        with self.lock:
            return [dict(n) for n in self.items.values() if n["id"] not in self.dismissed]


BOARD = Board()


def reset():
    """A fresh board for a new run (a test calling run() twice starts clean)."""
    global BOARD
    BOARD = Board()
    return BOARD


def warn(key, text, level="warn", action=None, board=None):
    """Print a start-up warning as before (stderr) and show it on the banner (without its "warning: ")."""
    print(text, file=sys.stderr)
    shown = text[len("warning: "):] if text.startswith("warning: ") else text
    (board or BOARD).set(key, shown[:1].upper() + shown[1:], level, action)
