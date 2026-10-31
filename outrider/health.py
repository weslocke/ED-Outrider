"""What kind of failure a call to an outside service met (the uploads' Recent list and outage alert, S3/S16), and
whether the read-only lookups are answering (S42). No network of its own.

`classify(exc, status, text)` -> (kind, user_fix): kind is one of KINDS, user_fix True when the player can fix it on
their side (no DNS, no network at all). `HttpError` is a sender's own "the service answered HTTP <status>", a
ConnectionError (so the upload loop backs off as for any network failure) that keeps the status for classify.

`Health`: per lookup source (SOURCES: Spansh, EDSM, GitHub, EDAstro, Canonn) whether it is down, fed by an aiohttp
TraceConfig on the lookups' one session (`trace_config`: every request, so no call site reports anything itself). A
failure counts only when no answer from that source came since the request began (one slow request among fifty
answered ones is not an outage); "No internet connection" only when two or more sources failed by DNS or no route with
no answer from anywhere between. A failure is forgotten after DOWN_FRESH_S with nothing asked since (a daily check that
failed once is not "down" all day). A certificate failure (issue #9: the clock, or a root this PC's store lacks) keeps
its words (outrider.tls.cert_text: the host and the fix) for the Data tile and its own banner card. The uploads have
their own record (outrider.uploads.Recent); bio.py's rules check (urllib, on a worker) is not counted.
"""
import asyncio
import errno
import re
import socket
import ssl
import time
from urllib.parse import urlsplit

from . import tls

# dns: the name not found; offline: no route to it (this machine's network down); refused: nothing listening there;
# timeout: no answer in time; certificate: the service's certificate could not be verified (this PC's clock, or a root
# its store has not fetched: outrider.tls); tls: the secure connection failed otherwise; http5xx: the service failing;
# rate: asked to slow down; http4xx: a request it refused; bad_answer: an answer that is not what the service answers;
# other: anything else
KINDS = ("dns", "offline", "refused", "timeout", "certificate", "tls", "http5xx", "rate", "http4xx", "bad_answer", "other")
USER_FIX = frozenset({"dns", "offline"})
# words in a 4xx answer that mean "too many requests" (Inara says it in its header's text, with a 400: inara.RATE_WORDS)
RATE_WORDS = ("slow down", "too many", "too much", "rate limit", "revoked", "temporarily")
_OFFLINE = {errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENETDOWN}
_CODE = re.compile(r"^\s*(\d{3})\b")


class HttpError(ConnectionError):
    """A service answered with an HTTP status that is not an answer to read (EDSM's or Inara's non-200)."""

    def __init__(self, status, text):
        super().__init__(text)
        self.status = status


def _by_status(status, text=""):
    if 500 <= status <= 599:
        return "http5xx"
    if 400 <= status <= 499:
        return "rate" if status == 429 or any(w in (text or "").lower() for w in RATE_WORDS) else "http4xx"
    return "bad_answer"


def _chain(exc):
    """The exception and what it wraps (urllib's reason, __cause__, __context__, aiohttp's os_error), each once."""
    seen = []
    while exc is not None and exc not in seen and len(seen) < 8:
        seen.append(exc)
        reason = getattr(exc, "reason", None)
        exc = getattr(exc, "os_error", None) or (reason if isinstance(reason, BaseException) else None) \
            or exc.__cause__ or exc.__context__
    return seen


def classify(exc=None, status=None, text=None):
    """(kind, user_fix) for a failure: a raised exception, an HTTP status, or a service's answer text that starts
    with its code ("503 busy", "400 Too much requests, slow down")."""
    kind = None
    if exc is not None:
        if isinstance(exc, HttpError) or (status is None and isinstance(getattr(exc, "status", None), int)):
            kind = _by_status(status or exc.status, str(exc))   # aiohttp's ClientResponseError carries one too
        elif status is None:   # a status further down the chain (readclient.Unreachable raised from an HTTP 503 or 429:
            # complete review 2026-10-30, it was "failed" / "refused")
            e = next((e for e in _chain(exc)[1:] if isinstance(e, HttpError) or isinstance(getattr(e, "status", None), int)), None)
            if e is not None:   # aiohttp's own text needs its request; its message is the reason
                kind = _by_status(e.status, str(e) if isinstance(e, HttpError) else str(getattr(e, "message", "") or ""))
        for e in () if kind else _chain(exc):
            name = type(e).__name__
            if isinstance(e, socket.gaierror) or name == "ClientConnectorDNSError":
                kind = "dns"
            elif tls.cert_failure(e) is not None:
                kind = "certificate"
            elif isinstance(e, ssl.SSLError | ssl.CertificateError) or "SSL" in name or "Certificate" in name:
                kind = "tls"
            elif isinstance(e, asyncio.TimeoutError | TimeoutError) or "Timeout" in name:
                kind = "timeout"
            elif isinstance(e, ConnectionRefusedError) or name == "ServerDisconnectedError":
                kind = "refused"
            elif isinstance(e, OSError) and e.errno in _OFFLINE:
                kind = "offline"
            elif isinstance(e, ValueError) or name in ("ContentTypeError", "ClientPayloadError"):
                kind = "bad_answer"   # JSONDecodeError is a ValueError; so is our own "no msgnum"
            elif isinstance(e, ConnectionError):
                kind = "refused"      # reset, aborted, or a sender's own "unreachable"
            if kind:
                break
    elif status is not None:
        kind = _by_status(status, text or "")
    elif text:
        m = _CODE.match(text)
        # a retry answer with no code of its own: the service is having trouble
        kind = _by_status(int(m.group(1)), text) if m else "http5xx"
    kind = kind or "other"
    return kind, kind in USER_FIX


# ---- the read-only lookups' health (S42) ----

SOURCES = {"spansh": "Spansh", "edsm": "EDSM", "github": "GitHub", "edastro": "EDAstro", "canonn": "Canonn"}
HOSTS = {"spansh.co.uk": "spansh", "www.spansh.co.uk": "spansh", "www.edsm.net": "edsm", "edsm.net": "edsm",
         "api.github.com": "github", "github.com": "github", "raw.githubusercontent.com": "github",
         "edastro.com": "edastro", "www.edastro.com": "edastro",
         "us-central1-canonn-api-236217.cloudfunctions.net": "canonn"}
DOWN_FRESH_S = 1800     # a failure with nothing asked of that source since is forgotten after this
OFFLINE = "No internet connection"


def source_of_host(url):
    """The lookup source a URL's host belongs to, or None."""
    try:
        return HOSTS.get((urlsplit(str(url)).hostname or "").lower())
    except ValueError:
        return None


def short_text(source):
    """The Data tile's words for a source that is down: "Spansh unavailable" (no detail: the author's choice)."""
    return f"{SOURCES.get(source, source)} unavailable"


class Health:
    """Which lookup sources are down: `ok(source, at)` and `failed(source, exc, status, started, at)` from the trace,
    `down()` for the payload, `offline()`, `text(source)` (the short form, "No internet connection" first), `expire(now)`
    (the periodic check). `on_change` is called whenever down() or offline() changes."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self.last_ok = {}     # source -> when it last answered
        self.out = {}         # source -> {since, last, kind, user_fix, error, fails}
        self.no_net = {}      # source -> when it last failed by dns/offline, since the last answer from anywhere
        self.on_change = None

    def _changed(self):
        if self.on_change:
            self.on_change()

    def ok(self, source, at=None):
        at = self.clock() if at is None else at
        self.last_ok[source] = at
        # something answered: the network is up, so another source's "no network" failure is out of date too (it is
        # asked again by its own caller)
        gone = {source} | {s for s, o in self.out.items() if o["user_fix"]}
        changed = bool(gone & set(self.out))
        for s in gone:
            self.out.pop(s, None)
        self.no_net.clear()
        if changed:
            self._changed()

    def failed(self, source, exc=None, status=None, started=None, at=None, host=None):
        """A request to `source` failed. Ignored when the source answered another request since this one began.
        True when it counted. A certificate failure keeps its words (outrider.tls.cert_text, naming `host`)."""
        at = self.clock() if at is None else at
        if started is not None and self.last_ok.get(source, -1) >= started:
            return False
        kind, user_fix = classify(exc, status)
        was, offline = self.out.get(source, {}).get("kind"), self.offline()
        o = self.out.setdefault(source, {"since": at, "fails": 0})
        o.update(last=at, kind=kind, user_fix=user_fix, fails=o["fails"] + 1,
                 error=f"{type(exc).__name__}: {exc}"[:300] if exc is not None else f"HTTP {status}",
                 text=tls.cert_text(exc, host) if kind == "certificate" else None)
        if user_fix:
            self.no_net[source] = at
        # a source newly down, the network's state turned, or a certificate failure begun or ended (it has its own card)
        if was is None or offline != self.offline() or (kind == "certificate") != (was == "certificate"):
            self._changed()
        return True

    def offline(self):
        return len(self.no_net) >= 2

    def expire(self, now=None):
        """Forget failures nothing has asked about for DOWN_FRESH_S. True when that changed anything."""
        now = self.clock() if now is None else now
        old = [s for s, o in self.out.items() if now - o["last"] >= DOWN_FRESH_S]
        for s in old:
            self.out.pop(s)
            self.no_net.pop(s, None)
        if old:
            self._changed()
        return bool(old)

    def down(self):
        """[{source, name, since, kind, user_fix, text}] in SOURCES' order (timestamps, never ticking text); text: a
        certificate failure's words (outrider.tls.cert_text), else None."""
        return [{"source": s, "name": SOURCES.get(s, s), "since": self.out[s]["since"], "kind": self.out[s]["kind"],
                 "user_fix": self.out[s]["user_fix"], "text": self.out[s].get("text")} for s in sorted(self.out, key=lambda s: list(SOURCES).index(s)
                                                                      if s in SOURCES else 99)]

    def is_down(self, source):
        return source in self.out

    def text(self, source):
        """The status line's words for a failed lookup of `source`: the short form, no detail."""
        return OFFLINE if self.offline() else short_text(source)

    def summary(self):
        """The payload's `health` (the Data tile only: the banner is the notices board's)."""
        return {"down": self.down(), "offline": self.offline()}

    def trace_config(self, source_of=source_of_host):
        """An aiohttp TraceConfig that reports every request of the session it is given to: a response under 500 (but
        429) is an answer, a 5xx, a 429 or an exception a failure. `source_of(url)` names the source (None: not one)."""
        from aiohttp import TraceConfig

        async def start(session, ctx, params):
            ctx.started = self.clock()

        async def end(session, ctx, params):
            src = source_of(params.url)
            if not src:
                return
            st = params.response.status
            if st >= 500 or st == 429:
                self.failed(src, status=st, started=getattr(ctx, "started", None))
            else:
                self.ok(src)

        async def exception(session, ctx, params):
            src = source_of(params.url)
            if src and not isinstance(params.exception, asyncio.CancelledError):
                self.failed(src, params.exception, started=getattr(ctx, "started", None),
                            host=urlsplit(str(params.url)).hostname)

        tc = TraceConfig()
        tc.on_request_start.append(start)
        tc.on_request_end.append(end)
        tc.on_request_exception.append(exception)
        return tc
