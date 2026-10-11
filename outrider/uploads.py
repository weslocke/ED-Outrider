"""Uploads (EDDN, EDSM; Inara later): the shared foundation. Opt-in, off by default (PLAN-edmc-functionality part A).

Pure where it can be; the server (ed_outrider.py) owns the database, the sender tasks and the settings.

- Session: what the journal says about the game session a line belongs to: the game version and build of each journal
  file (its Fileheader), the commander, Horizons / Odyssey (LoadGame only: a key LoadGame leaves out stays out), where
  you are (SystemAddress, StarSystem, StarPos together, from Location / FSDJump / CarrierJump only), whether you are
  crew in someone else's ship, the body you are at, the station you are docked at, your ship. EDDN's and EDSM's rules
  need all of it (research-edmc-2026-10-08/eddn.md, edsm-inara.md).
- UploadHub: every line of a live journal folder passes through `line()` before the reader's own filter. The startup
  scan feeds the session only ("catchup"); only the running tail ("live") may queue, and only lines no older than
  MAX_AGE_S by this machine's clock: a re-read, a rebuild, a restore or a legacy folder never uploads anything. The
  first line seen from a file primes the session from the top of that file, so a restart mid-file still knows the
  version, the commander and where you are.
- The outbox (`upload_queue`, live only): a message is queued in the same transaction as the line that made it, so a
  tick rolled back drops it too; UNIQUE(service, source) keeps a line handled twice (a retried tick, a twin folder)
  from being queued twice. Senders take rows after the commit.
"""
import copy
import json
import os
import re
import sqlite3
import time

from outrider.core import ts_seconds

MAX_AGE_S = 7 * 86400    # a line older than this (by this machine's clock) is never uploaded, even on a catch-up (the
#                          author's cap: a forgotten instance must not send months of play; listeners may refuse old data)
SKEW_S = 300             # ...and one stamped this far in the future still counts (the game PC's clock ahead)
SOURCE_RE = re.compile(r"^Journal(Beta|Alpha)?\.")
_OLD_NAME = re.compile(r"^(Journal(?:Beta|Alpha)?)\.(\d\d)(\d\d)(\d\d)(\d{6})\.(\d+)\.log$")


def name_key(name):
    """A journal file name in time order: the old form (Journal.YYMMDDhhmmss.NN.log, before 2023) as the new one
    (Journal.YYYY-MM-DDThhmmss.NN.log), so a 2021 file never sorts after a 2026 one. Marks keep the real name; every
    comparison of positions goes through this (pos_key). (A game started in the repeated hour after a clock change
    can still sort out of order: the names are local time.)"""
    base = os.path.basename(str(name))
    m = _OLD_NAME.match(base)
    if m:
        kind, yy, mo, dd, hms, part = m.groups()
        return f"{kind}.20{yy}-{mo}-{dd}T{hms}.{int(part):02d}.log"
    return base


def pos_key(pos):
    """A position (file name, offset) in time order."""
    return (name_key(pos[0]), pos[1])

SCHEMA = """
-- Outgoing uploads (EDDN, EDSM), live only: queued in the tick that read the line (a rollback drops them), sent after
-- its commit by the sender tasks. state: queued, sent, dropped (refused for good), dry (a developer's dry run: built,
-- not sent). next_try: when it may go (EDSM's events wait for a jump or docking, at most a few minutes). Kept a week after sending (the UNIQUE check and the status view), then pruned. Not in
-- RESET_JOURNAL_DATA: a journal re-read uploads nothing and must not forget what was sent.
CREATE TABLE IF NOT EXISTS upload_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT, service TEXT NOT NULL, schema TEXT, source TEXT NOT NULL, created TEXT,
    cmdr TEXT, gameversion TEXT, gamebuild TEXT, message TEXT, state TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0, next_try REAL NOT NULL DEFAULT 0, last_status TEXT, done_at REAL,
    UNIQUE (service, source));
CREATE INDEX IF NOT EXISTS upload_queue_state ON upload_queue (service, state, id);
-- The "New to EDSM" badge's table, gone (EDDN's copy of a jump usually reaches EDSM first, so EDSM's systemCreated
-- seldom names your upload): dropped from databases that had it.
DROP TABLE IF EXISTS edsm_new_systems;
"""


def _seconds(ts):
    """A journal timestamp as epoch seconds, or None for anything else."""
    try:
        return ts_seconds(str(ts))
    except (TypeError, ValueError):
        return None


def version_tuple(v):
    """'4.0.0.1904' -> (4, 0, 0, 1904); () when it has no leading number."""
    out = []
    for part in str(v or "").strip().split("."):
        m = re.match(r"\d+", part)
        if not m:
            break
        out.append(int(m.group(0)))
    return tuple(out)


class Session:
    """The game session a journal line belongs to (see the module doc). feed() every line of the live folders, in
    order; nothing here reads the clock or the database."""

    def __init__(self):
        self.versions = {}    # journal file name -> (gameversion, build) from its Fileheader (or LoadGame)
        self.file = None      # the file of the line being fed
        self.cmdr = self.fid = None
        self.horizons = self.odyssey = None   # None: LoadGame did not say (EDDN: leave the key out)
        self.addr = self.system = self.pos = None
        self.crew = False     # crew in another commander's ship: nothing of it is uploaded
        self.body = self.body_id = None       # the body you approached (journal), until LeaveBody / a jump
        self.status_body = None               # Status.json's BodyName (set by the hub from the live reading)
        self.status_pos = None                # its (Latitude, Longitude, BodyName, timestamp) on a body (scanorganic)
        self.market_id = self.station = None
        self.ship_id = None
        self.dir = None                       # the journal folder of the line (NavRoute.json, Market.json... live there)
        self.pending = {}                     # what waits on a companion file or the next line (EDDN's waits)
        self.source = None                    # the line being handled ("file:offset"; the hub sets it), and
        self.now = None                       # ...the server's clock then (EDDN's waits give up by it)

    # ---- what the line's session is ----
    @property
    def gameversion(self):
        return (self.versions.get(self.file) or ("", ""))[0]

    @property
    def gamebuild(self):
        return (self.versions.get(self.file) or ("", ""))[1]

    @property
    def beta(self):
        m = SOURCE_RE.match(self.file or "")
        return bool(m and m.group(1)) or any(w in self.gameversion.lower() for w in ("alpha", "beta"))

    @property
    def legacy(self):
        """The Legacy galaxy (a 3.x client): nobody takes its data (EDSM 208, Inara; EDDN's live schemas skip it)."""
        v = version_tuple(self.gameversion)
        return bool(v) and v < (4,)

    def blocked(self):
        """Why nothing from this session may be uploaded now, or None: 'beta', 'legacy', 'crew', 'version' (no
        game version known yet), 'commander' (none yet)."""
        if self.beta:
            return "beta"
        if self.legacy:
            return "legacy"
        if self.crew:
            return "crew"
        if not self.gameversion:
            return "version"
        if not self.cmdr:
            return "commander"
        return None

    def located(self, addr):
        """Whether the tracked position is this SystemAddress (EDDN adds StarSystem/StarPos only then)."""
        return addr is not None and self.addr is not None and addr == self.addr and self.pos is not None

    # ---- following the journal ----
    def _clear_place(self):
        self.addr = self.system = self.pos = None
        self.body = self.body_id = None

    def feed(self, ev, file=None):
        if file:
            self.file = file
        name = ev.get("event")
        if name == "Fileheader":
            self.versions[self.file] = (str(ev.get("gameversion") or ""), str(ev.get("build") or ""))
            if continued(ev):   # part 2 or later of a long session: no LoadGame follows, the session goes on
                return
            self.cmdr = self.fid = None
            self.horizons = self.odyssey = None
            self.crew = False
            self._clear_place()
        elif name == "Commander":
            self.cmdr, self.fid = ev.get("Name") or self.cmdr, ev.get("FID") or self.fid
        elif name == "LoadGame":
            self.cmdr, self.fid = ev.get("Commander") or self.cmdr, ev.get("FID") or self.fid
            self.horizons = bool(ev["Horizons"]) if "Horizons" in ev else None
            self.odyssey = bool(ev["Odyssey"]) if "Odyssey" in ev else None
            if self.file not in self.versions and ev.get("gameversion"):
                self.versions[self.file] = (str(ev.get("gameversion") or ""), str(ev.get("build") or ""))
            self.ship_id = ev.get("ShipID", self.ship_id)
            self.crew = False
            self._clear_place()
            self.market_id = self.station = None
        elif name in ("Location", "FSDJump", "CarrierJump"):
            pos = ev.get("StarPos")
            self.addr = ev.get("SystemAddress")
            self.system = ev.get("StarSystem")
            self.pos = list(pos) if isinstance(pos, (list, tuple)) and len(pos) == 3 else None
            if name == "FSDJump":
                self.body = self.body_id = None
                self.market_id = self.station = None
            else:   # a Location or a carrier's jump: docked or not, at a body or not, as it says
                docked = ev.get("Docked") and not ev.get("Taxi") and not ev.get("Multicrew")
                self.market_id, self.station = (ev.get("MarketID"), ev.get("StationName")) if docked else (None, None)
                if ev.get("BodyType") in ("Planet", "Star") or ev.get("Body"):
                    self.body, self.body_id = ev.get("Body"), ev.get("BodyID")
                elif name == "Location":
                    self.body = self.body_id = None
        elif name == "ApproachBody":
            self.body, self.body_id = ev.get("Body"), ev.get("BodyID")
        elif name == "LeaveBody":
            self.body = self.body_id = None
        elif name == "Docked":
            if not ev.get("Taxi") and not ev.get("Multicrew"):
                self.market_id, self.station = ev.get("MarketID"), ev.get("StationName")
        elif name == "Undocked":
            self.market_id = self.station = None
        elif name in ("Loadout", "ShipyardSwap", "SetUserShipName"):
            self.ship_id = ev.get("ShipID", self.ship_id)
        elif name == "ShipyardBuy":
            self.ship_id = None
        elif name == "JoinACrew":
            self.crew = bool(ev.get("Captain")) and ev.get("Captain") != self.cmdr
            self._clear_place()
        elif name == "QuitACrew":
            self.crew = False
            self._clear_place()

    def snapshot(self):
        return copy.deepcopy(self.__dict__)

    def restore(self, snap):
        self.__dict__.update(copy.deepcopy(snap))


def continued(ev):
    """Whether a Fileheader starts a continuation file (part 2 or later): the game moved a long session on to a new
    file after a Continued line, with no LoadGame after it."""
    try:
        return ev.get("event") == "Fileheader" and int(ev.get("part") or 1) > 1
    except (TypeError, ValueError):
        return False


def continued_from(path):
    """The journal a continuation file (continued) goes on from: the one before it in its folder, or None."""
    try:
        with open(path, "rb") as f:
            first = json.loads(f.readline() or b"{}")
    except (OSError, ValueError):
        return None
    if not isinstance(first, dict) or not continued(first):
        return None
    files = glob_journals(os.path.dirname(path))
    name = name_key(path)
    before = [p for p in files if name_key(p) < name]
    return before[-1] if before else None


def live_line(ts, now, max_age=MAX_AGE_S, skew=SKEW_S):
    """Whether a line stamped `ts` is recent enough to upload at `now` (both epoch-ish: ts a journal timestamp)."""
    t = _seconds(ts)
    return t is not None and -skew <= now - t <= max_age


# ---- the outbox ----

def enqueue(db, service, schema, source, ts, session, message, next_try=0):
    """Queue one message (in the caller's transaction), to go from next_try (epoch seconds; 0: now). False when that
    line was queued for that service already."""
    cur = db.execute("INSERT OR IGNORE INTO upload_queue (service, schema, source, created, cmdr, gameversion, gamebuild,"
                     " message, next_try) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (service, schema, source, ts, session.cmdr, session.gameversion, session.gamebuild,
                      json.dumps(message, separators=(",", ":")), next_try))
    return cur.rowcount > 0


def deadline(db, service):
    """When what of `service` waits for company goes at the latest: the first waiting message's time, which later
    ones join (so a long stay sends one batch, not each message on its own clock). None when nothing waits."""
    return db.execute("SELECT MIN(next_try) FROM upload_queue WHERE service=? AND state='queued' AND attempts=0"
                      " AND next_try > 0", (service,)).fetchone()[0]


def release(db, service):
    """What of `service` waits for company (never tried yet) may go now."""
    db.execute("UPDATE upload_queue SET next_try = 0 WHERE service=? AND state='queued' AND attempts=0 AND next_try > 0",
               (service,))


def due(db, service, now, limit=50):
    """Rows of `service` to send now, oldest first."""
    return [dict(r) if isinstance(r, sqlite3.Row) else r for r in db.execute(
        "SELECT * FROM upload_queue WHERE service=? AND state='queued' AND next_try <= ? ORDER BY id LIMIT ?",
        (service, now, limit))]


def settle(db, row_id, state, status, now, retry_in=None):
    """A send's outcome: sent / dropped (done_at stamped), or queued again after retry_in seconds."""
    if state == "queued":
        db.execute("UPDATE upload_queue SET attempts = attempts + 1, next_try = ?, last_status = ? WHERE id = ?",
                   (now + (retry_in or 60), status, row_id))
    else:
        db.execute("UPDATE upload_queue SET state = ?, last_status = ?, done_at = ?, attempts = attempts + 1 WHERE id = ?",
                   (state, status, now, row_id))


def prune(db, now, keep_s=7 * 86400):
    """Forget sent and dropped rows older than keep_s."""
    db.execute("DELETE FROM upload_queue WHERE state IN ('sent', 'dropped', 'dry') AND done_at < ?", (now - keep_s,))


def counts(db, service):
    """{queued, sent_24h, dropped_24h, dry_24h, last_sent} for the status view."""
    now = time.time()
    q = lambda sql, *a: db.execute(sql, (service,) + a).fetchone()[0]
    last = db.execute("SELECT done_at, last_status FROM upload_queue WHERE service=? AND state='sent' "
                      "ORDER BY done_at DESC LIMIT 1", (service,)).fetchone()
    return {"queued": q("SELECT count(*) FROM upload_queue WHERE service=? AND state='queued'"),
            "sent_24h": q("SELECT count(*) FROM upload_queue WHERE service=? AND state='sent' AND done_at > ?", now - 86400),
            "dropped_24h": q("SELECT count(*) FROM upload_queue WHERE service=? AND state='dropped' AND done_at > ?",
                             now - 86400),
            "dry_24h": q("SELECT count(*) FROM upload_queue WHERE service=? AND state='dry' AND done_at > ?", now - 86400),
            "last_sent": last[0] if last else None}


def position(path_or_name, offset):
    """A journal line's place, comparable across instances reading the same folder: (file name, byte offset). Journal
    file names sort by their time."""
    return (os.path.basename(path_or_name), int(offset))


class UploadHub:
    """Every live-folder line goes through line(). builders: {service: fn(ev, session) -> [(schema, message)]}: what a
    line uploads to that service (the EDDN and EDSM parts add theirs). enabled(service) -> bool says which are on now
    (the settings, the leases, simulate). holds: {service: fn(ev) -> seconds}: how long that service's messages from
    this line may wait for others (EDSM's batches); 0 sends what waits, the line's own included.

    Each service has a mark (marks[service] = [file name, offset, timestamp]): how far its lines have been queued. A
    line is queued only after its service's mark, at most MAX_AGE_S old, from a session nothing blocks; the mark then
    moves on. The mark survives a journal re-read (it lives in the database's meta, not in the journal tables), so a
    re-read sends nothing again; catch_up() sends what was played while Outrider was not running (from the mark to
    where the start-up scan got to). A service with no mark yet starts at the line it first sees (switching it on
    sets one: State.set_upload)."""

    def __init__(self, db, builders=None, enabled=None, clock=time.time, max_age=MAX_AGE_S, save=None, holds=None,
                 max_ages=None, idlers=None, follow=None, quiet=None):
        self.db = db
        self.builders = dict(builders or {})
        self.holds = dict(holds or {})
        self.idlers = dict(idlers or {})   # {service: fn(session) -> [(schema, message, source line)]}: idle()
        self.enabled = enabled or (lambda service: False)
        # follow(service): wanted though not queueing now (another uploader has it): its mark moves with the lines,
        # so nothing that uploader sent is caught up later
        self.follow = follow or (lambda service: False)
        # quiet(ev, session): a live line a service does not build (another uploader has it): what it was waiting on
        # in the session is dropped, so nothing from that stretch goes once it builds again (EDDN's waits)
        self.quiet = dict(quiet or {})
        self.clock, self.max_age = clock, max_age
        self.max_ages = dict(max_ages or {})   # {service: seconds}: a service's own limit, under max_age (EDDN's hour)
        self.save = save                 # save(marks): stores the marks (State: meta upload_marks)
        self.session = Session()
        self.primed = set()              # files whose top this session has read
        self.queued = 0                  # messages queued since start (the status view)
        self.marks, self.marks_dirty = {}, False

    def active(self):
        """Whether any service wants the lines (queueing, or following another uploader's)."""
        return any(self.enabled(s) or self.follow(s) for s in self.builders)

    def forget(self):
        """No service wants the lines (the reader stops passing them): what the session knew goes stale from here,
        so it is dropped, and the next line wanted primes its file from the top again (status_body is the live
        Status.json's, kept)."""
        if self.primed:
            body, pos = self.session.status_body, self.session.status_pos
            self.session, self.primed = Session(), set()
            self.session.status_body, self.session.status_pos = body, pos

    def prime(self, path, upto, session=None, depth=0):
        """Feed a session the lines of `path` before byte `upto` (state only): a file met part way through. A
        continuation file is primed from the file it goes on from first (who and where you are were said there)."""
        session = session or self.session
        if session is self.session:
            self.primed.add(os.path.basename(path))
        prev = continued_from(path) if depth < 20 else None
        if prev:
            try:
                self.prime(prev, os.path.getsize(prev), session, depth + 1)
            except OSError:
                pass
        try:
            with open(path, "rb") as f:
                data = f.read(upto)
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

    def after_mark(self, service, pos):
        m = self.marks.get(service)
        return m is None or pos_key((m[0], m[1])) < pos_key(pos)

    def set_mark(self, service, pos, ts=None):
        self.marks[service] = [pos[0], pos[1], ts]
        self.marks_dirty = True

    def flush(self):
        """Store the marks (in the tick's transaction) when they moved."""
        if self.marks_dirty and self.save:
            self.save(dict(self.marks))
        self.marks_dirty = False

    def _queue(self, ev, b, offset, session, services):
        """Build and queue `ev` for each of `services` (whose mark it is after), moving their marks."""
        n = 0
        pos = position(b, offset)
        now = self.clock()
        session.source, session.now = f"{b}:{offset}", now
        for service in services:
            if not self.after_mark(service, pos):
                continue
            self.set_mark(service, pos, ev.get("timestamp"))
            if not live_line(ev.get("timestamp"), now, min(self.max_age, self.max_ages.get(service, self.max_age))) \
                    or session.blocked():
                continue
            try:
                messages = self.builders[service](ev, session) or []
            except (KeyError, TypeError, ValueError, AttributeError, IndexError) as e:   # an odd line: skip it
                print(f"{service}: a line could not be prepared ({type(e).__name__}: {e})")
                continue
            wait = self.holds[service](ev) if service in self.holds else 0
            if service in self.holds and not wait:
                release(self.db, service)
            go = 0
            if wait and messages:   # joins the batch already waiting (its deadline), or starts one
                go = deadline(self.db, service) or self.clock() + wait
            for i, (schema, message) in enumerate(messages):
                if enqueue(self.db, service, schema, f"{b}:{offset}" + (f"#{i}" if i else ""), ev.get("timestamp"),
                           session, message, go):
                    n += 1
        self.queued += n
        return n

    def line(self, path, offset, raw, mode):
        """One journal line (bytes) at `offset` of `path`. mode: "catchup" (the start-up scan: state only) or "live"
        (the running tail: may queue). Returns the number of messages queued. Database errors propagate."""
        b = os.path.basename(path)
        if b not in self.primed:
            self.prime(path, offset)
        self.session.dir = os.path.dirname(path)
        try:
            ev = json.loads(raw)
        except ValueError:
            return 0
        if not isinstance(ev, dict):
            return 0
        self.session.feed(ev, b)
        if mode != "live":
            return 0
        on = [s for s in self.builders if self.enabled(s)]
        pos = position(b, offset)
        for s in self.builders:
            if s not in on and s in self.quiet:
                self.quiet[s](ev, self.session)
            if s not in on and self.follow(s) and self.after_mark(s, pos):
                self.set_mark(s, pos, ev.get("timestamp"))
        return self._queue(ev, b, offset, self.session, on)

    def catch_up(self, service, dirs, upto):
        """Queue what `service` missed: the live folders' lines after its mark, up to where the reader has got to
        (upto: {path: offset}, the start-up scan's), through a session of their own. Lines over MAX_AGE_S old only
        move the mark. A line already queued is not queued again (the outbox's UNIQUE). Returns the number queued."""
        if service not in self.builders or service not in self.marks:
            return 0
        start = name_key(self.marks[service][0])
        files = {}
        for d in dirs:
            for p in glob_journals(d):
                b = os.path.basename(p)
                if name_key(b) >= start and (b not in files or upto.get(p, 0) > upto.get(files[b], 0)):
                    files[b] = p
        n = 0
        session = Session()
        first = files[min(files, key=name_key)] if files else None
        prev = continued_from(first) if first else None
        if prev:   # the first file goes on from an earlier one: who and where you are come from there
            try:
                self.prime(prev, os.path.getsize(prev), session)
            except OSError:
                pass
        for b in sorted(files, key=name_key):
            p = files[b]
            end = upto.get(p)
            if end is None:
                continue
            try:
                with open(p, "rb") as f:
                    data = f.read(end)
            except OSError:
                continue
            session.dir = os.path.dirname(p)
            at = 0
            for raw in data.split(b"\n"):
                here, at = at, at + len(raw) + 1
                if not raw.strip() or at > end + 1:
                    continue
                try:
                    ev = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(ev, dict):
                    continue
                session.feed(ev, b)
                n += self._queue(ev, b, here, session, [service])
        n += self._catch_up_tail(service, session)
        self.flush()
        return n

    def _catch_up_tail(self, service, session):
        """What waited at the end of a catch-up: no further line comes inside it, so the service's idle step runs as
        if the quiet spell had passed (a batch of signals ending the journal was dropped with the catch-up's session:
        the Fable sweep, 2026-10-09). A batch not yet located (Odyssey writes a jump's signals before its FSDJump)
        goes over to the live session, whose next line (that FSDJump) sends it. Returns the number queued."""
        n = 0
        # a companion file's wait (Market.json, NavRoute.json...) is not aged with the signals: its file may still be
        # on its way (a journal share), and an aged wait was given up (Codex F2, 2026-10-09)
        files = {k: w for k, w in session.pending.items() if k not in ("signals", "signals_since")}
        if service in self.idlers and not session.blocked():
            for k in files:
                session.pending.pop(k)
            for now, waiting in ((self.clock() + 60, {}), (self.clock(), files)):   # signals past any quiet spell, short
                session.now = now                                                 # of every give-up; then the files
                session.pending.update(waiting)
                n += self._idle_queue(service, session)
        left = session.pending.get("signals")
        if left and self.session.file == session.file and "signals" not in self.session.pending:
            self.session.pending["signals"] = list(left)
            self.session.pending["signals_since"] = dict(session.pending.get("signals_since") or {}, at=self.clock())
        for k in files:   # still waiting: the live session's tick sends it when the file comes, inside its wait
            w = session.pending.get(k)
            if isinstance(w, dict) and w.get("origin") and self.session.file == session.file and k not in self.session.pending:
                self.session.pending[k] = dict(w, since=self.clock())
        self.queued += n
        return n

    def _idle_queue(self, service, session):
        """The service's idle step on `session`, its messages queued. Returns the number queued."""
        try:
            messages = self.idlers[service](session) or []
        except (KeyError, TypeError, ValueError, AttributeError, IndexError):
            messages = []
        n = 0
        for schema, message, origin in messages:
            ts = (message.get("message") or message).get("timestamp") if isinstance(message, dict) else None
            if origin and enqueue(self.db, service, schema, f"{origin}#{schema}", ts, session, message):
                n += 1
        return n

    def idle(self):
        """The server's tick with no new line: what the services can send now anyway (EDDN: a companion file written
        late, signals after a quiet spell), each under the line it comes from. Returns the number queued."""
        s = self.session
        if not self.idlers or s.blocked():
            return 0
        s.now, n = self.clock(), 0
        for service, fn in self.idlers.items():
            if not self.enabled(service):
                continue
            try:
                messages = fn(s) or []
            except (KeyError, TypeError, ValueError, AttributeError, IndexError) as e:
                print(f"{service}: waiting data could not be prepared ({type(e).__name__}: {e})")
                continue
            for schema, message, origin in messages:
                ts = (message.get("message") or message).get("timestamp") if isinstance(message, dict) else None
                if origin and enqueue(self.db, service, schema, f"{origin}#{schema}", ts, s, message):
                    n += 1
        self.queued += n
        return n

    def status(self, st):
        """The live Status.json reading: the body it names (EDDN's codex entries say it only then) and, on a body, where
        you are on it with the reading's time (EDDN's scanorganic, only when it matches the scan)."""
        st = st or {}
        live = bool(st.get("live"))
        self.session.status_body = st.get("body") if live else None
        self.session.status_pos = (st.get("lat"), st.get("lon"), st.get("body"), st.get("ts")) \
            if live and st.get("lat") is not None and st.get("lon") is not None and st.get("body") else None

    def snapshot(self):
        return (self.session.snapshot(), set(self.primed), self.queued, copy.deepcopy(self.marks), self.marks_dirty)

    def restore(self, snap):
        s, primed, self.queued, marks, self.marks_dirty = snap
        self.session.restore(s)
        self.primed = set(primed)
        self.marks = copy.deepcopy(marks)


def glob_journals(d):
    """A folder's journals, oldest first (name_key)."""
    import glob
    return sorted(glob.glob(os.path.join(glob.escape(d), "Journal.*.log")), key=name_key)


# ---- settings ----

SERVICES = ("eddn", "edsm")
DEFAULTS = {"eddn": {"enabled": False}, "edsm": {"enabled": False}}
TEST_ENV = "OUTRIDER_EDDN_TEST"   # a developer's switch, not a setting: EDDN's /test schemas while trying sender code


def upload_settings(cfg):
    """[eddn] enabled and [edsm] enabled from the config (written there by Settings -> Uploads, the only place to
    switch them; hidden from the Server settings): bools, anything else off."""
    out = {}
    for service, keys in DEFAULTS.items():
        sec = cfg.get(service) if isinstance(cfg.get(service), dict) else {}
        out[service] = {k: sec[k] if isinstance(sec.get(k), bool) else v for k, v in keys.items()}
    return {"uploads": out}


def eddn_test_mode(environ=None):
    """Whether EDDN messages go to its test schemas: only when the developer starts Outrider with OUTRIDER_EDDN_TEST=1
    (EDDN asks that new sender code be tried there first). Players have no setting for it: the switch to send is in
    Settings -> Uploads, and that is the only one."""
    environ = os.environ if environ is None else environ
    return str(environ.get(TEST_ENV, "")).strip().lower() in ("1", "true", "yes", "on")


# ---- sending ----

GAP_S = 0.5              # between two sends of one service while the queue drains (EDDN: about 2 a second)
IDLE_S = 2.0             # how often an empty or switched-off queue is looked at
BACKOFF_S = (60, 120, 300, 600, 1800)   # after a network failure or a 5xx: at least a minute (EDDN's rule), growing


async def upload_loop(service, db, send, on, clock=time.time, sleep=None, report=None, batch=50):
    """Drain `service`'s outbox while it is on: send(rows) -> [(row id, state, status text, retry_in or None)] for
    each row it settled (state: sent, dropped, queued (retry after retry_in), held (stop until the player acts)); a raised
    exception is a network failure: those rows wait BACKOFF_S. report(service, outcome dict) after each round (the
    status view). Runs until cancelled."""
    import asyncio
    sleep = sleep or asyncio.sleep
    fails = 0
    while True:
        try:
            if not on(service):
                await sleep(IDLE_S)
                continue
            rows = due(db, service, clock(), batch)
        except sqlite3.Error as e:   # the database busy or broken for a moment: the sender stays alive
            print(f"{service}: outbox not read ({e})")
            await sleep(IDLE_S)
            continue
        if not rows:
            await sleep(IDLE_S)
            continue
        now = clock()
        wait = 0
        try:
            results = await send(rows)
            error = None
            retry = [r for _, st, _, r in results if st == "queued"]
            if retry:   # the service said later (a 5xx, a rate limit): the whole queue waits, not just these rows
                wait = max(max(x or 0 for x in retry), BACKOFF_S[min(fails, len(BACKOFF_S) - 1)])
                fails += 1
                error = next(status for _, st, status, _ in results if st == "queued")
            else:
                fails = 0
        except Exception as e:   # unreachable, a timeout, a 5xx raised by the sender: wait, then again
            wait = BACKOFF_S[min(fails, len(BACKOFF_S) - 1)]
            fails += 1
            results = [(r["id"], "queued", f"{type(e).__name__}: {e}"[:300], wait) for r in rows]
            error = f"{type(e).__name__}: {e}"
        try:
            for row_id, state, status, retry_in in results:
                if state == "held":
                    db.execute("UPDATE upload_queue SET last_status = ? WHERE id = ?", (status, row_id))
                else:
                    settle(db, row_id, state, status, now, max(retry_in or 0, wait) if state == "queued" else retry_in)
            db.commit()
        except sqlite3.Error as e:   # not recorded: those rows go again (the services drop duplicates)
            try:
                db.rollback()
            except sqlite3.Error:
                pass
            error = f"outbox not updated ({e})"
            wait = max(wait, IDLE_S)
        if report:
            report(service, {"error": error, "results": results, "at": now})
        if any(state == "held" for _, state, _, _ in results):
            await sleep(IDLE_S * 15)   # waiting on the player (a refused key): look again now and then
        else:
            await sleep(wait or GAP_S)


# ---- one uploader at a time: lease files in the journal folder (the author's idea, 2026-10-08) ----

LEASE_DIR = ".outrider"   # a subfolder of the journal folder: Elite and other tools read only its top level
LEASE_STALE_S = 300       # another instance's lease counts while its content changed this recently (by OUR clock)
LEASE_ABANDONED_S = 3600  # ...and one first seen untouched this long (its mtime: the file server's clock, hence the hour)
#                           is stale at once: a crash's leftover from long ago does not block uploads after a start


def lease_path(journal_dir, instance):
    return os.path.join(journal_dir, LEASE_DIR, f"uploads-{instance}.json")


def write_lease(journal_dir, instance, info):
    """Write (atomically) this instance's lease, or remove it when info is None. False when the folder cannot be
    written (a read-only mount: other instances then cannot see this one)."""
    path = lease_path(journal_dir, instance)
    try:
        if info is None:
            if os.path.exists(path):
                os.remove(path)
            return True
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(info, f)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


class Leases:
    """The other instances' leases, judged by when their content last changed as seen by this instance's own clock
    (the two machines' clocks are never compared). A crashed instance's file goes stale after LEASE_STALE_S."""

    def __init__(self, instance, clock=time.time):
        self.instance, self.clock = instance, clock
        self.seen = {}   # path -> (content, when we saw it change)

    def others(self, journal_dirs):
        """{instance id: {host, services, wanted, legacy}} of the live leases in these folders (not ours). services:
        what it sends; wanted: what it is switched on for (sending, or giving way to another); legacy: a lease from
        before `wanted` (2026.10.19), whose services are everything it wants, sending or not."""
        now, out = self.clock(), {}
        for d in journal_dirs:
            folder = os.path.join(d, LEASE_DIR)
            try:
                names = os.listdir(folder)
            except OSError:
                continue
            for n in names:
                m = re.fullmatch(r"uploads-([A-Za-z0-9_-]+)\.json", n)
                if not m or m.group(1) == self.instance:
                    continue
                path = os.path.join(folder, n)
                try:
                    with open(path, encoding="utf-8") as f:
                        content = f.read()
                    info = json.loads(content)
                except (OSError, ValueError):
                    continue
                prev = self.seen.get(path)
                if not prev:
                    # first sight: one left by a crash long ago is stale now, not LEASE_STALE_S from now. Its mtime
                    # comes from another clock (the file server's), hence the margin
                    try:
                        old = now - os.path.getmtime(path) > LEASE_ABANDONED_S
                    except OSError:
                        old = False
                    self.seen[path] = prev = (content, now - LEASE_STALE_S - 1 if old else now)
                elif prev[0] != content:
                    self.seen[path] = prev = (content, now)
                if now - prev[1] <= LEASE_STALE_S and isinstance(info, dict):
                    sends = [s for s in info.get("services") or [] if s in SERVICES]
                    legacy = not isinstance(info.get("wanted"), list)
                    out[m.group(1)] = {"host": str(info.get("host") or "another Outrider"), "services": sends,
                                       "wanted": sends if legacy else [s for s in info["wanted"] if s in SERVICES],
                                       "legacy": legacy}
        return out


def lease_owners(instance, wanted, sending, others):
    """{service: None (this instance sends it) or the host it gives way to} for each service in `wanted`, so exactly
    one of the Outriders switched on for a service sends it. One already sending keeps it; when none is, or two are
    (both started before seeing the other), the lowest instance id has it: a rule every instance works out the same
    way, with no clocks compared. A legacy lease (an Outrider from before this rule, which holds whenever another
    lease names the service) is always given way to: it then sends. `sending`: what this instance sends now."""
    out = {}
    for s in wanted:
        rivals = {iid: o for iid, o in others.items() if s in o["wanted"]}
        legacy = next((o for o in rivals.values() if o["legacy"]), None)
        senders = {iid: o for iid, o in rivals.items() if s in o["services"]}
        if legacy:
            out[s] = legacy["host"]
        elif senders:
            first = min(senders)
            out[s] = None if s in sending and instance < first else senders[first]["host"]
        else:   # nobody else sends it: this one keeps it if it does, else the lowest id of those deciding
            first = min(rivals, default=None)
            out[s] = None if s in sending or first is None or instance < first else rivals[first]["host"]
    return out


def lease_marks(journal_dirs, instance):
    """The furthest mark per service in the other instances' lease files, live or not (a stopped instance leaves its
    file with no services and its last marks: a handover note). {service: [file, offset, ts]}."""
    out = {}
    for d in journal_dirs:
        folder = os.path.join(d, LEASE_DIR)
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for n in names:
            m = re.fullmatch(r"uploads-([A-Za-z0-9_-]+)\.json", n)
            if not m or m.group(1) == instance:
                continue
            try:
                with open(os.path.join(folder, n), encoding="utf-8") as f:
                    info = json.load(f)
            except (OSError, ValueError):
                continue
            for service, mark in ((info or {}).get("marks") or {}).items() if isinstance(info, dict) else ():
                if service in SERVICES and isinstance(mark, list) and len(mark) >= 2 and isinstance(mark[1], int):
                    if service not in out or pos_key(mark) > pos_key(out[service]):
                        out[service] = list(mark[:3])
    return out


def edmc_uploads(home=None, environ=None, platform=None, running=None):
    """Whether EDMarketConnector on THIS computer is running with its own EDDN / EDSM / Inara uploads on:
    {running, eddn, edsm, inara} or None when it is not installed here. Its config is config.toml (EDMC 6) in
    ~/.local/share/EDMarketConnector (Linux) or %LOCALAPPDATA%\\EDMarketConnector (Windows): settings.output has
    the EDDN bits (1 station data, 2048 the rest), edsm_out and inara_out are 0/1."""
    import sys
    try:
        import tomllib
    except ImportError:  # Python < 3.11
        return None
    environ = os.environ if environ is None else environ
    platform = platform or sys.platform
    home = home or os.path.expanduser("~")
    if platform == "win32":
        base = environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
    else:
        base = environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    path = os.path.join(base, "EDMarketConnector", "config.toml")
    try:
        with open(path, "rb") as f:
            st = tomllib.load(f).get("settings") or {}
    except (OSError, ValueError):
        return None
    out = int(st.get("output") or 0) if str(st.get("output") or "0").lstrip("-").isdigit() else 0
    is_running = running() if running else edmc_running(platform)
    return {"running": bool(is_running), "eddn": bool(out & (1 | 2048)), "edsm": bool(st.get("edsm_out")),
            "inara": bool(st.get("inara_out"))}


def edmc_running(platform):
    """Whether an EDMarketConnector process runs on this computer (Linux: /proc; Windows: tasklist)."""
    if platform == "win32":
        import subprocess
        try:
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq EDMarketConnector.exe", "/NH"], capture_output=True,
                                 text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            return False
        return "EDMarketConnector" in out
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except OSError:
        return False
    for p in pids:
        try:
            with open(f"/proc/{p}/cmdline", "rb") as f:
                if b"EDMarketConnector" in f.read():
                    return True
        except OSError:
            continue
    return False
