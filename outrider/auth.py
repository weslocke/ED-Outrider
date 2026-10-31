"""Sign-in for devices on the network: [server] password (the tablet and its Android app).

Requests from this PC itself (loopback) never need it. From any other address every page and /api/ route needs a
session, except the few that must stay open (/api/version, the sign-in itself, the overlays' /api/status).

A session token is "<id>.<signature>": the id is random, the signature an HMAC of it under a key made from the
password and a per-install secret (kept in the database). So a token survives an Outrider restart (no list of tokens
in memory), every token dies when the password changes, and signing out puts that one id on a revoked list.
"""
import hashlib
import hmac
import ipaddress
import re
import secrets
import time

COOKIE = "outrider_session"
SIGNIN_TRIES = 5        # failed sign-ins per address...
SIGNIN_WINDOW = 60      # ...in this many seconds, then 429 until the oldest failure is a window old
TOKEN_SIG_HEX = 32


def new_secret():
    return secrets.token_hex(32)


def _key(secret, password):
    return hmac.new(secret.encode(), b"outrider-session|" + password.encode(), hashlib.sha256).digest()


def _sign(secret, password, sid):
    return hmac.new(_key(secret, password), sid.encode(), hashlib.sha256).hexdigest()[:TOKEN_SIG_HEX]


def make_token(secret, password):
    """A new session token for this password."""
    sid = secrets.token_urlsafe(12)
    return f"{sid}.{_sign(secret, password, sid)}"


def token_id(token):
    """The id part of a token (for signing out), or None for something that is not one."""
    if not isinstance(token, str) or token.count(".") != 1:
        return None
    sid, sig = token.split(".")
    # only the shape make_token makes: a url-safe id and a hex signature (anything else, non-ASCII above all, would
    # make hmac.compare_digest raise: review 2026-10-08 #11)
    ok = re.fullmatch(r"[A-Za-z0-9_-]+", sid) and re.fullmatch(rf"[0-9a-f]{{{TOKEN_SIG_HEX}}}", sig)
    return sid if ok else None


def check_token(secret, password, token, revoked=()):
    """Whether `token` is a live session for this password (constant-time on the signature)."""
    sid = token_id(token)
    if not sid or not password or not secret or sid in revoked:
        return False
    return hmac.compare_digest(token.split(".")[1], _sign(secret, password, sid))


def password_ok(given, password):
    """Constant-time comparison of a sign-in attempt with the configured password."""
    return isinstance(given, str) and bool(password) and hmac.compare_digest(given.encode(), password.encode())


def is_loopback(remote):
    """Whether a peer address is this machine (127.0.0.0/8, ::1, or an IPv4-mapped loopback)."""
    try:
        ip = ipaddress.ip_address(str(remote or "").split("%")[0])
    except ValueError:
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    return ip.is_loopback or bool(mapped and mapped.is_loopback)


FORWARD_HEADERS = ("X-Forwarded-For", "Forwarded", "X-Real-IP")


def from_this_pc(remote, headers):
    """Whether a request comes from this machine itself: a loopback peer that no proxy forwarded. A reverse proxy on
    this PC (Caddy, nginx: docs/guide/install.md) connects from loopback for every device it serves, and says so in a
    forwarding header; such a request is another device's (review 2026-10-08 #3: the password was bypassed). Caddy
    adds the header by itself, nginx only with a proxy_set_header line (the guide gives it)."""
    return is_loopback(remote) and not any(headers.get(h) for h in FORWARD_HEADERS)


def client_key(remote, headers, trust_headers=True):
    """Who to count wrong passwords against: the peer, or, behind a reverse proxy on this PC, the client it names (the
    last hop it added). Headers from any other peer are not trusted: anyone can send them. Nor inside a container
    (trust_headers False, the caller's LOOPBACK_TRUSTED): rootless port forwarding delivers every outside connection
    from loopback with the client's own headers, so a new X-Forwarded-For on each try was a new count (complete
    review 2026-10-30)."""
    if trust_headers and is_loopback(remote):
        fwd = (headers.get("X-Forwarded-For") or "").split(",")[-1].strip() or (headers.get("X-Real-IP") or "").strip()
        if fwd:
            return fwd
        if headers.get("Forwarded"):   # RFC 7239: the last for= (the hop the proxy added), else one shared bucket
            hops = re.findall(r'for="?\[?([^;,\]"\s]+)', headers["Forwarded"], re.IGNORECASE)
            return hops[-1] if hops else "forwarded"
    return str(remote)


def request_token(headers, cookies):
    """The session token a request carries: `Authorization: Bearer <token>` (the app's own calls) or the cookie."""
    auth = headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return cookies.get(COOKIE) or None


def version_tuple(v):
    """'1.2.10' -> (1, 2, 10), a build suffix ignored ('1.0.0-debug', '1.1.0+5'); anything unreadable -> () (older
    than every version)."""
    try:
        return tuple(int(x) for x in re.split(r"[-+]", str(v).strip(), maxsplit=1)[0].split("."))
    except ValueError:
        return ()


class RateLimit:
    """Failed sign-ins per address: SIGNIN_TRIES in SIGNIN_WINDOW seconds, then wait."""

    def __init__(self, tries=SIGNIN_TRIES, window=SIGNIN_WINDOW, clock=time.monotonic):
        self.tries, self.window, self.clock = tries, window, clock
        self.failures = {}

    def _recent(self, who):
        now = self.clock()
        kept = [t for t in self.failures.get(who, []) if now - t < self.window]
        if kept:
            self.failures[who] = kept
        else:
            self.failures.pop(who, None)
        return kept

    def wait(self, who):
        """Seconds until `who` may try again (0: now)."""
        recent = self._recent(who)
        if len(recent) < self.tries:
            return 0
        return max(1, int(self.window - (self.clock() - recent[0])) + 1)

    def failed(self, who):
        now = self.clock()
        # every address whose last failure is out of the window goes: one that never tries again is not kept for the
        # life of an always-on Outrider
        self.failures = {k: v for k, v in self.failures.items() if v and now - v[-1] < self.window}
        self._recent(who)
        self.failures.setdefault(who, []).append(now)

    def clear(self, who):
        self.failures.pop(who, None)
