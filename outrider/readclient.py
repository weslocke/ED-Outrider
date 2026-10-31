"""The EDSM and Inara read client (G3): what Outrider asks of the player's own accounts, never an upload. The requests
and the parsers are pure; `fetch` makes one call through a session and a pace the server gives it (EDSM's reads
EDSM_GAP_S apart; Inara's one gate, shared with its sender: outrider.uploads.Gate).

Keys go in a POST body, never in a URL: an aiohttp error's text carries the URL, and an error's text is never put in an
answer anyway (`reach_words` says only what kind of failure it was).

EDSM (www.edsm.net/en/api-commander-v1, api-logs-v1): get-credits (S45's key check: msgnum 100 the name and the key go
together, 203 they do not), get-position and get-logs (S47 and S67: where EDSM's flight log ends, what it
holds for a window of at most a week). Inara (inara.cz/elite/inara-api-docs): getCommanderProfile (S45's key check: the
header's 400 refuses the key, the event's 204 finds no such commander, 200 is the profile with its link). The shapes
are the services' documented ones (tests/fixtures/account_checks.json); their live replies are still to be checked.

The long reads (S67's import, S47's Check and guard) ride out a passing failure with `retrying`: the same request again
after each of RETRY_WAITS_S while it fails in a way that passes (`transient`: no answer, or EDSM failing or saying try
later: `try_later`), then the failure raises. A refusal (a wrong key, a malformed answer) raises at once. Reads only:
a request retried here stores nothing anywhere.
"""
import asyncio
import time

from outrider.health import HttpError, classify

EDSM_CREDITS_URL = "https://www.edsm.net/api-commander-v1/get-credits"
EDSM_POSITION_URL = "https://www.edsm.net/api-logs-v1/get-position"
EDSM_LOGS_URL = "https://www.edsm.net/api-logs-v1/get-logs"
EDSM_GAP_S = 2.0                  # between two of EDSM's account reads, at least
EDSM_LOGS_WINDOW_S = 7 * 86400    # get-logs answers at most a week per request
RETRY_WAITS_S = (30, 60, 120, 300, 600)   # s before each new try of a read that failed in passing; then it stops (~20 min)
TRANSIENT = frozenset({"dns", "offline", "refused", "timeout", "http5xx", "rate"})   # health.classify's kinds that pass
_sleep = asyncio.sleep            # retrying's wait (tests replace it)
SLOW_WORDS = ("slow down", "too many", "too much", "rate limit", "try again later", "temporarily")   # in EDSM's msg
URLS = ("EDSM_CREDITS_URL", "EDSM_POSITION_URL", "EDSM_LOGS_URL")   # verify.sh points each at a closed port

EDSM_CODES = {201: "commander name missing", 202: "API key missing", 203: "commander name or API key not found",
              208: "no credits stored yet"}
# what kind of failure, in the words of "Couldn't reach Inara: timeout"
REACH_WORDS = {"dns": "its address is not found (is this PC online?)", "offline": "no network",
               "refused": "the connection was refused", "timeout": "timeout",
               "certificate": "its certificate could not be verified (check this PC's date and time)",
               "tls": "the secure connection failed",
               "http5xx": "it is failing (HTTP 5xx)", "rate": "it asked Outrider to slow down",
               "http4xx": "it refused the request", "bad_answer": "its answer was not understood", "other": "failed"}


def _code(reply, field="msgnum"):
    if not isinstance(reply, dict):
        raise ValueError("the answer is not a JSON object")
    try:
        return int(reply.get(field))
    except (TypeError, ValueError):
        raise ValueError(f"the answer has no {field}")


def edsm_form(name, key, **extra):
    """The POST body (form fields) of an EDSM account read: the EDSM commander name and the API key, then extras."""
    return {"commanderName": str(name), "apiKey": str(key), **{k: str(v) for k, v in extra.items() if v is not None}}


def edsm_credits_answer(reply):
    """get-credits' reply -> {ok, code, text, balance}: 100 the name and key go together (S45), 203 they do not; 208
    they do, with no credits stored yet (a new account before its first upload: complete review 2026-10-30, it read as
    refused)."""
    code = _code(reply)
    text = str(reply.get("msg") or "")
    if code == 208:
        return {"ok": True, "code": code, "text": EDSM_CODES[208], "balance": None}
    if code == 100:
        rows = reply.get("credits") if isinstance(reply.get("credits"), list) else []
        bal = rows[0].get("balance") if rows and isinstance(rows[0], dict) else None
        return {"ok": True, "code": code, "text": text or "OK", "balance": bal if isinstance(bal, (int, float)) else None}
    return {"ok": False, "code": code, "text": EDSM_CODES.get(code) or text or "refused", "balance": None}


def _edsm_date(s):
    """EDSM's "2026-10-09 21:14:05" (UTC) -> "2026-10-09T21:14:05Z", or None."""
    s = str(s or "").strip()
    return s.replace(" ", "T") + "Z" if len(s) == 19 and s[4] == "-" and s[10] == " " else None


def _coords(c):
    if isinstance(c, dict) and all(isinstance(c.get(k), (int, float)) for k in "xyz"):
        return {k: float(c[k]) for k in "xyz"}
    return None


def edsm_position_request(name, key):
    """get-position's body: the last system EDSM's flight log has, with its ids and coordinates."""
    return edsm_form(name, key, showId=1, showCoordinates=1)


def edsm_position_answer(reply):
    """get-position's reply -> {ok, code, text, system, id64, coords, date}."""
    code = _code(reply)
    if code != 100:
        return {"ok": False, "code": code, "text": EDSM_CODES.get(code) or str(reply.get("msg") or "refused")}
    id64 = reply.get("systemId64")
    return {"ok": True, "code": code, "text": "OK", "system": reply.get("system") or None,
            "id64": id64 if isinstance(id64, int) else None, "coords": _coords(reply.get("coordinates")),
            "date": _edsm_date(reply.get("date"))}


def edsm_logs_request(name, key, start, end):
    """get-logs' body for a window [start, end) in epoch seconds, at most EDSM_LOGS_WINDOW_S long (EDSM's own limit)."""
    if end - start > EDSM_LOGS_WINDOW_S:
        raise ValueError("get-logs answers at most a week per request")
    fmt = lambda t: time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t))
    return edsm_form(name, key, startDateTime=fmt(start), endDateTime=fmt(end), showId=1, showCoordinates=1)


def edsm_logs_answer(reply):
    """get-logs' reply -> {ok, code, text, logs: [{system, id64, coords, date, first_discover, ship_id}]}, oldest first."""
    code = _code(reply)
    if code != 100:
        return {"ok": False, "code": code, "text": EDSM_CODES.get(code) or str(reply.get("msg") or "refused"), "logs": []}
    logs = []
    for e in reply.get("logs") if isinstance(reply.get("logs"), list) else []:
        if not isinstance(e, dict) or not e.get("system") or not _edsm_date(e.get("date")):
            continue
        id64 = e.get("systemId64")
        logs.append({"system": str(e["system"]), "id64": id64 if isinstance(id64, int) else None,
                     "coords": _coords(e.get("coordinates")), "date": _edsm_date(e["date"]),
                     "first_discover": bool(e.get("firstDiscover")), "ship_id": e.get("shipId")})
    logs.sort(key=lambda e: e["date"])
    return {"ok": True, "code": code, "text": "OK", "logs": logs}


def inara_profile_request(key, commander, version, software, developing=False, when=None):
    """Inara's getCommanderProfile for the key's own commander (searchName: the in-game name): one event, no upload."""
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if when is None else when))
    return {"header": {"appName": software, "appVersion": version, "isBeingDeveloped": bool(developing),
                       "APIkey": key, "commanderName": commander},
            "events": [{"eventName": "getCommanderProfile", "eventTimestamp": ts, "eventData": {"searchName": commander}}]}


def inara_profile_answer(reply, rate_words=()):
    """getCommanderProfile's reply -> {ok, code, text, name, url, rate}: the header's 400 refuses the key (rate: Inara
    asked to slow down instead), the event's 204 finds no such commander, 200 is the profile."""
    head = reply.get("header") if isinstance(reply, dict) else None
    code = _code(head, "eventStatus")
    text = str(head.get("eventStatusText") or "")
    if code >= 400:
        rate = any(w in text.lower() for w in rate_words)
        return {"ok": False, "code": code, "text": text or "refused", "rate": rate, "name": None, "url": None}
    events = reply.get("events") if isinstance(reply.get("events"), list) else []
    e = events[0] if events and isinstance(events[0], dict) else {}
    n = _code(e, "eventStatus")
    if n != 200:
        return {"ok": False, "code": n, "text": str(e.get("eventStatusText") or "no such commander"), "rate": False,
                "name": None, "url": None}
    d = e.get("eventData") if isinstance(e.get("eventData"), dict) else {}
    url = d.get("inaraURL")
    return {"ok": True, "code": n, "text": "OK", "rate": False, "name": d.get("commanderName") or d.get("userName"),
            "url": url if isinstance(url, str) and url.startswith("https://inara.cz/") else None}


async def fetch(session, url, gate, data=None, body=None):
    """One POST (form `data` or JSON `body`) after the gate lets it go -> the decoded JSON. A status other than 200
    raises HttpError (its text names the status only); a timeout, no network... raise as aiohttp does."""
    await gate.wait()
    kw = {"data": data} if data is not None else {"json": body}
    async with session.post(url, **kw) as r:
        if r.status != 200:
            raise HttpError(r.status, f"HTTP {r.status}")
        return await r.json(content_type=None)


class TryLater(HttpError):
    """EDSM answered, but with a failure of its own (msgnum 5xx): the same request may work later."""


class Unreachable(Exception):
    """A service still failing in passing when `retrying` ran out, named (source: "Spansh", "EDSM"); raised from the
    failure itself, so health.classify and reach_words read its kind through __cause__."""

    def __init__(self, source):
        super().__init__(f"{source} not reached")
        self.source = source


def try_later(got):
    """An EDSM read's parsed answer -> itself; one saying slow down raises HttpError 429 (health's "rate"), one saying
    EDSM is failing (msgnum 500 and up) raises TryLater (HTTP 5xx). Any other refusal is the caller's to read."""
    if not got.get("ok"):
        if any(w in str(got.get("text") or "").lower() for w in SLOW_WORDS):
            raise HttpError(429, f"EDSM {got.get('code')}")
        if isinstance(got.get("code"), int) and got["code"] >= 500:
            raise TryLater(got["code"] if got["code"] <= 599 else 503, f"EDSM {got['code']}")
    return got


def transient(exc):
    """The kind of a failure that passes (TRANSIENT: a timeout, no connection, no DNS, a 5xx, a slow down), else None."""
    kind = classify(exc)[0]
    return kind if kind in TRANSIENT else None


async def retrying(call, waiting=None, waits=None):
    """await call() -> its answer, asked again after each of `waits` (RETRY_WAITS_S) while it raises a transient failure;
    waiting(attempt, attempts, at, exc) before each wait (the next attempt's number, how many in all, its epoch time).
    The last failure, or any that does not pass, raises."""
    waits = RETRY_WAITS_S if waits is None else waits
    for k in range(len(waits) + 1):
        try:
            return await call()
        except Exception as e:
            if k == len(waits) or not transient(e):
                raise
            if waiting:
                waiting(k + 2, len(waits) + 1, time.time() + waits[k], e)
            await _sleep(waits[k])


def reach_words(exc):
    """What kind of failure a call met, in a few words ("timeout"), never its text (which can carry the URL)."""
    return REACH_WORDS.get(classify(exc)[0], "failed")
