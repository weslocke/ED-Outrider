"""Filling a gap in EDSM's flight log (S47), pure: what Outrider would send to EDSM for a stretch of time it never sent,
rebuilt from the journals. The server (ed_outrider.py) owns the Check against EDSM's log, the guard, the queue and the
sending (service "edsm_bf"); nothing here touches the network or the database.

- rebuild(): every journal file that can hold the range (the live folders, the legacy ones and the backups' journal
  archive, one copy per file name: the largest), read in time order through a Session of its own, as the live uploader
  reads them; each line of the range, of that commander, that EDSM wants (edsm.build, minus its discard list) becomes a
  row keyed like the outbox's ("<file>:<byte offset>"), so a second start never queues a line twice.
- summary(): what a Preview says: events by name, the jumps among them, the requests and the time they take.
- windows(): the range cut into get-logs' week-long windows (the guard asks each: EDSM must have nothing there).

The one deliberate exception to the uploads' 7-day cap (uploads.MAX_AGE_S): explicit, ranged, previewed, and checked
against EDSM's own log first (docs/DESIGN_NOTES.md).
"""
import calendar
import json
import os
import re
import time

from outrider import edsm, uploads
from outrider.core import iso_ts

MAX_EVENTS = 50000      # a Preview larger than this asks for a shorter range
SEND_GAP_S = 10         # between two backfill requests: gentle, EDSM's own uploads come first
_WHEN = re.compile(r"^(\d{4})-(\d\d)-(\d\d)[ T](\d\d):(\d\d)(?::(\d\d))?Z?$")
_STAMP = re.compile(r"^Journal(?:Beta|Alpha)?\.(\d{4}-\d\d-\d\dT\d{6})\.")


def parse_when(text):
    """'2026-10-09 21:14' / '2026-10-09 21:14:05' / '2026-10-09T21:14:05Z' (UTC) -> epoch seconds, else None."""
    m = _WHEN.match(str(text or "").strip())
    if not m:
        return None
    y, mo, d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    try:
        t = calendar.timegm((y, mo, d, h, mi, s, 0, 0, 0))
        return t if time.gmtime(t)[:6] == (y, mo, d, h, mi, s) else None   # 2026-02-30 is not a date
    except (OverflowError, ValueError):
        return None


def windows(start, end, size):
    """[start, end) cut into windows of at most `size` seconds, oldest first."""
    out, t = [], start
    while t < end:
        out.append((t, min(end, t + size)))
        t += size
    return out


def journal_files(dirs):
    """{file name: path} over `dirs`, one per name: the largest copy (a live file can be ahead of its archived copy)."""
    best = {}
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for p in uploads.glob_journals(d):
            b = os.path.basename(p)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            if b not in best or size > best[b][0]:
                best[b] = (size, p)
    return {b: p for b, (_, p) in best.items()}


def files_for(files, start, end):
    """The file names that can hold [start, end), in time order. Names are local time: a day of slack each side, and
    the file started last before that, which may run into the range."""
    lo = time.strftime("%Y-%m-%dT%H%M%S", time.gmtime(start - 86400))
    hi = time.strftime("%Y-%m-%dT%H%M%S", time.gmtime(end + 86400))
    names = sorted(files, key=uploads.name_key)
    stamps = [(b, (_STAMP.match(uploads.name_key(b)) or [None, ""])[1]) for b in names]
    first = next((i for i, (_, s) in enumerate(stamps) if s >= lo), len(stamps))
    return [b for b, s in stamps[max(0, first - 1):] if s < hi]


def _feed_file(session, path, upto=None):
    try:
        with open(path, "rb") as f:
            data = f.read() if upto is None else f.read(upto)
    except OSError:
        return
    for raw in data.split(b"\n"):
        if raw.strip():
            try:
                ev = json.loads(raw)
            except ValueError:
                continue
            if isinstance(ev, dict):
                session.feed(ev, os.path.basename(path))


def rebuild(dirs, start, end, commander, discard=edsm.DISCARD, skip=frozenset(), left_out=None):
    """The EDSM rows for journal time [start, end) of `commander`: ([{source, ts, event, cmdr, gameversion, gamebuild,
    message}] in journal order, files read). `skip`: sources already in the outbox for EDSM's live stream (never sent
    twice). Lines of a beta, a Legacy client or a crew session are left out, as the live uploader leaves them; a dict
    `left_out` gets their count per reason (uploads.Session.blocked: legacy, beta, crew, ...), so an empty Preview can
    say why (S7-S6)."""
    files = journal_files(dirs)
    chosen = files_for(files, start, end)
    lo, hi = iso_ts(start), iso_ts(end)
    session, rows = uploads.Session(), []
    if chosen:   # a continuation goes on from an earlier file: who and where you are were said there
        chain, p = [], uploads.continued_from(files[chosen[0]])
        while p and len(chain) < 20:
            chain.insert(0, p)
            p = uploads.continued_from(p)
        for p in chain:
            _feed_file(session, p)
    for b in chosen:
        try:
            with open(files[b], "rb") as f:
                data = f.read()
        except OSError:
            continue
        end_at = data.rfind(b"\n") + 1   # the game may be mid-write on the last line
        at = 0
        for raw in data[:end_at].split(b"\n")[:-1]:
            here, at = at, at + len(raw) + 1
            if not raw.strip():
                continue
            try:
                ev = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(ev, dict):
                continue
            session.feed(ev, b)
            ts = ev.get("timestamp")
            if not isinstance(ts, str) or not lo <= ts < hi or session.cmdr != commander:
                continue
            why = session.blocked()
            if why:
                if left_out is not None and edsm.build(ev, session, discard):   # a line EDSM would have had
                    left_out[why] = left_out.get(why, 0) + 1
                continue
            for i, (name, message) in enumerate(edsm.build(ev, session, discard)):
                source = f"{b}:{here}" + (f"#{i}" if i else "")
                if source in skip:
                    continue
                rows.append({"source": source, "ts": ts, "event": name, "cmdr": session.cmdr,
                             "gameversion": session.gameversion, "gamebuild": session.gamebuild, "message": message})
                if len(rows) > MAX_EVENTS:
                    raise ValueError(f"over {MAX_EVENTS:,} events: choose a shorter range")
    return rows, len(chosen)


def summary(rows, gap_s=SEND_GAP_S, batch=edsm.BATCH):
    """A Preview's figures: {events, by_event [[name, n]...] most first, jumps, requests, seconds, first, last}.
    Requests group as the sender does (edsm.same_batch: one game version per request, up to `batch` events)."""
    by = {}
    for r in rows:
        by[r["event"]] = by.get(r["event"], 0) + 1
    requests, i = 0, 0
    while i < len(rows):
        n = len(edsm.same_batch(rows[i:], batch))
        i += max(1, n)
        requests += 1
    return {"events": len(rows), "by_event": sorted(by.items(), key=lambda kv: (-kv[1], kv[0])),
            "jumps": by.get("FSDJump", 0) + by.get("CarrierJump", 0), "requests": requests,
            "seconds": max(0, requests - 1) * gap_s, "first": rows[0]["ts"] if rows else None,
            "last": rows[-1]["ts"] if rows else None}
