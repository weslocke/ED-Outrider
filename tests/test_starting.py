"""Progress while reading journals (S9): Outrider answers on its port at once with a starting page ("Reading your
journals: March 2024, 41%") while it opens the database, backs it up before a re-read (its own phase) and reads the
journals one file at a time on the event loop; /api/version keeps its shape, every other /api/ answers 503 "starting",
and the real app takes the port over when it is ready (GET /api/starting: "ready"). A stop during the import ends
between two files, each committed whole."""
import asyncio
import contextlib
import io
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
import unittest.mock
import urllib.error
import urllib.request

from support import ed_outrider
import outrider  # noqa: E402
import outrider.auth  # noqa: E402
import outrider.notices  # noqa: E402
import outrider.serverlog as L  # noqa: E402
import outrider.unsold  # noqa: E402


def write_journal(folder, name, lines=3):
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        for i in range(lines):
            f.write(json.dumps({"timestamp": f"2024-03-05T20:15:{i:02d}Z", "event": "Music", "MusicTrack": "Exploration"})
                    + "\n")
    return path


class Months(unittest.TestCase):
    def test_both_naming_styles(self):
        self.assertEqual(ed_outrider.journal_month("/j/Journal.2024-03-05T201512.01.log"), "March 2024")
        self.assertEqual(ed_outrider.journal_month("Journal.221231235959.01.log"), "December 2022")
        self.assertIsNone(ed_outrider.journal_month("Journal.2024-13-05T201512.01.log"))
        self.assertIsNone(ed_outrider.journal_month("Status.json"))
        self.assertIsNone(ed_outrider.journal_month(None))


class Steps(unittest.TestCase):
    """Journals.import_steps: a step after each file, committed; bytes read of those to read; a copy counted once."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.live, self.legacy = os.path.join(self.tmp.name, "live"), os.path.join(self.tmp.name, "legacy")
        os.makedirs(self.live)
        os.makedirs(self.legacy)
        self.dbp = os.path.join(self.tmp.name, "x.sqlite")
        self.db = ed_outrider.open_db(self.dbp)
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.files = [write_journal(self.live, n, k) for n, k in (("Journal.2024-03-05T201512.01.log", 3),
                                                                   ("Journal.2024-04-01T100000.01.log", 5),
                                                                   ("Journal.2024-05-01T100000.01.log", 2))]

    def rows(self):
        """journal_files as another connection sees it: what is committed."""
        con = sqlite3.connect(self.dbp)
        try:
            return dict(con.execute("SELECT path, offset FROM journal_files").fetchall())
        finally:
            con.close()

    def test_a_step_per_file(self):
        sizes = [os.path.getsize(p) for p in self.files]
        steps = []
        for step in self.j.import_steps([self.live]):
            steps.append(step)
            self.assertEqual(len(self.rows()), len(steps))   # committed before the step
        self.assertEqual([s["path"] for s in steps], self.files)
        self.assertEqual([s["done"] for s in steps], [sizes[0], sizes[0] + sizes[1], sum(sizes)])
        self.assertEqual({s["total"] for s in steps}, {sum(sizes)})
        self.assertEqual(list(self.j.import_steps([self.live])), [])   # read already: nothing left

    def test_legacy_first_each_file_committed_and_a_copy_counted_once(self):
        old = write_journal(self.legacy, "Journal.231231235959.01.log", 4)
        import shutil
        shutil.copy(self.files[0], self.legacy)   # the same file in both folders
        with unittest.mock.patch.object(ed_outrider, "LEGACY_DIRS", [self.legacy]), \
                contextlib.redirect_stdout(io.StringIO()):
            steps = []
            for step in self.j.import_steps([self.live]):
                steps.append(step)
                self.assertEqual(len(self.rows()), len(steps))   # a legacy file too (it used to be once per folder)
        # legacy first, in time order (name_key: the old name of 2023 before the new one of 2024)
        self.assertEqual([s["path"] for s in steps[:2]], [old, os.path.join(self.legacy, os.path.basename(self.files[0]))])
        self.assertEqual([s["path"] for s in steps[2:]], self.files[1:])   # the live copy of the first: read already
        sizes = sum(os.path.getsize(p) for p in self.files) + os.path.getsize(old)
        self.assertEqual(steps[-1]["total"], sizes)                    # the copy once
        self.assertEqual(steps[-1]["done"], sizes)
        self.assertTrue(ed_outrider.meta_get(self.db, f"legacy:{self.legacy}"))

    def test_a_stop_between_two_files(self):
        """import_journals: the stop is seen after a file is read and committed; nothing part read is kept."""
        starting = ed_outrider.Starting(stop=asyncio.Event())
        seen = []

        def step(s):
            seen.append(s["path"])
            starting.stop.set()   # SIGTERM arrives while the first file is read
        starting.step = step
        self.assertFalse(asyncio.run(ed_outrider.import_journals(self.j, [self.live], starting)))
        self.assertEqual(seen, self.files[:1])
        self.assertEqual(self.rows(), {self.files[0]: os.path.getsize(self.files[0])})   # whole, committed
        self.assertIsNone(self.j.upload_mode)   # the scan's own state put back
        starting.stop.clear()
        del starting.step
        self.assertTrue(asyncio.run(ed_outrider.import_journals(self.j, [self.live], starting)))   # the rest next time
        self.assertEqual(self.rows(), {p: os.path.getsize(p) for p in self.files})
        self.assertEqual((starting.done, starting.total, starting.path), (starting.total, starting.total, self.files[-1]))


class Reread(unittest.TestCase):
    """open_db(reset=False): the re-read is run()'s, in its own phases (the backup off the event loop, then the reset)."""

    def test_the_reset_split_out(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = os.path.join(tmp.name, "x.sqlite")
        db = ed_outrider.open_db(p)
        db.execute("INSERT INTO visits (id64, name) VALUES (1, 'Sol')")
        ed_outrider.meta_set(db, "parser_version", ed_outrider.PARSER_VERSION - 1)
        db.commit()
        db.close()
        db = ed_outrider.open_db(p, reset=False)
        self.addCleanup(db.close)
        self.assertEqual(ed_outrider.reread_due(db), (True, ed_outrider.PARSER_VERSION - 1))
        self.assertEqual(db.execute("SELECT count(*) FROM visits").fetchone()[0], 1)   # nothing cleared yet
        ed_outrider.reset_journal_data(db)
        self.assertEqual(db.execute("SELECT count(*) FROM visits").fetchone()[0], 0)
        self.assertEqual(ed_outrider.reread_due(db), (False, ed_outrider.PARSER_VERSION))
        self.assertEqual(ed_outrider.reread_due(db, rescan=True)[0], True)

    def test_the_backup_needs_no_connection(self):
        """On the worker thread the backup is given journals_gone's answer: it never touches the loop's connection."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = os.path.join(tmp.name, "x.sqlite")
        ed_outrider.open_db(p).close()
        board = outrider.notices.Board()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            out = ed_outrider.backup_before_reread(None, p, os.path.join(tmp.name, "b"), 3, board=board, gone=(9, 10))
        self.assertTrue(out["path"].endswith("-pre-reread.zip"))
        self.assertIn("9 of the 10 journal files", board.active()[0]["text"])


class Progress(unittest.TestCase):
    def test_words(self):
        s = ed_outrider.Starting()
        self.assertEqual(s.text(), "Opening the database")
        s.phase = "backup"
        self.assertEqual((s.text(), s.pct()), ("Backing up your database before reading every journal again", None))
        s.phase = "journals"
        self.assertEqual(s.text(), "Reading your journals")   # nothing to read
        s.step({"done": 41, "total": 100, "path": "/j/Journal.2024-03-05T201512.01.log"})
        self.assertEqual((s.text(), s.pct()), ("Reading your journals: March 2024, 41%", 41))
        s.step({"done": 100, "total": 100, "path": "/j/Status.json"})
        self.assertEqual(s.text(), "Reading your journals: 99%")   # 100 only once it serves
        self.assertEqual(s.info(details=False), {"phase": "starting", "text": "ED Outrider is starting", "pct": None,
                                                 "why": None, "since": None})


class StartingApp(unittest.TestCase):
    """make_starting_app: the page, /api/starting, /api/version as the real app's, 503 "starting" for the rest, the
    real app's guards; with a password, a device not signed in learns only that it is starting."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.log = L.ServerLog()
        self.log.feed("out", "re-reading every journal once\n")
        self.s = ed_outrider.Starting("", True, self.log)
        self.s.db = self.db
        self.s.phase = "journals"
        self.s.step({"done": 41, "total": 100, "path": "/j/Journal.2024-03-05T201512.01.log"})

    def ask(self, calls, remote_pc=True, real=False):
        from aiohttp.test_utils import TestClient, TestServer

        async def go():
            app = ed_outrider.make_app(ed_outrider.State(self.db, ed_outrider.Journals(self.db), None, 25)) if real \
                else ed_outrider.make_starting_app(self.s)
            out = []
            async with TestClient(TestServer(app)) as c:
                for method, path, headers in calls:
                    r = await c.request(method, path, headers=headers or {})
                    body = await r.text()
                    try:
                        body = json.loads(body)
                    except ValueError:
                        pass
                    out.append((r.status, body))
            return out
        with unittest.mock.patch.object(outrider.auth, "is_loopback", lambda remote: remote_pc):
            return asyncio.run(go())

    def test_answers(self):
        (page, tablet, starting, version, nearby, ask, static, log, foreign) = self.ask([
            ("GET", "/", None), ("GET", "/tablet", None), ("GET", "/api/starting", None), ("GET", "/api/version", None),
            ("GET", "/api/nearby?since=0:0", None), ("POST", "/api/ask", None), ("GET", "/static/page.js", None),
            ("GET", "/api/serverlog?after=0", None), ("POST", "/api/ask", {"Origin": "http://evil.example"})])
        self.assertEqual(page[0], 200)
        self.assertIn("ED Outrider is starting", page[1])
        self.assertIn('fetch("api/starting"', page[1])
        self.assertEqual(tablet, page)
        self.assertEqual(starting[1]["text"], "Reading your journals: March 2024, 41%")
        self.assertEqual((starting[1]["phase"], starting[1]["pct"]), ("journals", 41))
        real_version = self.ask([("GET", "/api/version", None)], real=True)[0][1]
        self.assertEqual(sorted(version[1]), sorted(real_version))   # the Android app's contract: the same keys
        self.assertEqual({k: version[1][k] for k in ("outrider", "api", "min_app", "password", "signed_in")},
                         {"outrider": outrider.__version__, "api": ed_outrider.API_VERSION,
                          "min_app": ed_outrider.MIN_APP_VERSION, "password": False, "signed_in": True})
        for status, body in (nearby, ask):
            self.assertEqual((status, body["code"]), (503, "starting"))
            self.assertEqual(body["error"], "Outrider is starting: Reading your journals: March 2024, 41%")
            self.assertEqual(body["starting"]["pct"], 41)
        self.assertEqual(static[0], 503)
        self.assertIn("ED Outrider is starting", static[1])
        self.assertEqual(log[1]["lines"][-1]["text"], "re-reading every journal once")   # Show log during a long re-read
        self.assertEqual(foreign[0], 403)   # another site's POST: refused before anything

    def test_a_device_not_signed_in(self):
        self.s.password = "hunter2"
        starting, version, nearby, log = self.ask([("GET", "/api/starting", None), ("GET", "/api/version", None),
                                                   ("GET", "/api/nearby", None), ("GET", "/api/serverlog", None)],
                                                  remote_pc=False)
        self.assertEqual(starting[1]["phase"], "starting")
        self.assertNotIn("41", json.dumps(starting[1]))
        self.assertEqual((version[1]["password"], version[1]["signed_in"]), (True, False))
        self.assertEqual((nearby[0], nearby[1]["code"], nearby[1]["error"]), (503, "starting", "Outrider is starting: ED Outrider is starting"))
        self.assertEqual((log[0], log[1]["code"]), (401, "signin_required"))
        # signed in (a session made by the running Outrider, its secret in the database): the details
        state = ed_outrider.State(self.db, ed_outrider.Journals(self.db), None, 25)
        state.password = "hunter2"
        token = state.new_session()
        starting, version = self.ask([("GET", "/api/starting", {"Authorization": f"Bearer {token}"}),
                                      ("GET", "/api/version", {"Authorization": f"Bearer {token}"})], remote_pc=False)
        self.assertEqual(starting[1]["pct"], 41)
        self.assertTrue(version[1]["signed_in"])
        self.s.db = None   # the database not open yet: no session can be checked
        self.assertEqual(self.ask([("GET", "/api/starting", {"Authorization": f"Bearer {token}"})], remote_pc=False)[0][1]["phase"],
                         "starting")

    def test_the_real_app_is_ready(self):
        (status, body), = self.ask([("GET", "/api/starting", None)], real=True)
        self.assertEqual((status, body["phase"]), (200, "ready"))


class Run(unittest.TestCase):
    """run(): the starting page answers on the port while the journals are read, and a stop then ends the start."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # run() sets the module's settings and folders as globals: put back for the other tests
        import inspect
        src = inspect.getsource(ed_outrider.run)
        names = [n.strip() for line in src.splitlines() if line.strip().startswith("global ")
                 for n in line.strip()[len("global "):].split(",")]
        saved = {n: getattr(ed_outrider, n) for n in names}
        unsold = {n: getattr(outrider.unsold, n) for n in ("LIVE_DIRS", "LEGACY_DIRS", "DEFAULT_DIRS")}
        board = outrider.notices.BOARD
        before = set(L._secrets)

        def put_back():
            for n, v in saved.items():
                setattr(ed_outrider, n, v)
            for n, v in unsold.items():
                setattr(outrider.unsold, n, v)
            outrider.notices.BOARD = board
            L._secrets.clear()
            L._secrets.update(before)
        self.addCleanup(put_back)

    def test_the_page_answers_while_reading_and_a_stop_ends_it(self):
        import socket
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        jdir = os.path.join(self.tmp.name, "journals")
        os.makedirs(jdir)
        path = write_journal(jdir, "Journal.2024-03-05T201512.01.log")
        cfg = os.path.join(self.tmp.name, "scratch.toml")
        with open(cfg, "w", encoding="utf-8") as f:
            f.write(f'[server]\nbackup_dir = "{self.tmp.name}/backups"\nbackup_every_days = 0\n'
                    f'[spansh]\nwatch_firsts = false\n[speech]\nserver_player = "off"\n')
        made, seen = [], {}

        class Recorded(ed_outrider.Starting):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                made.append(self)

        def slow_steps(journals, live_dirs):
            for i in range(1, 2000):
                time.sleep(0.003)   # a long journal file: the loop is busy, the page still answered between two
                if seen.get("done") or i == 1999:
                    made[0].stop.set()   # SIGTERM (the handler run() installs sets this)
                yield {"done": i, "total": 4000, "path": path}

        def browser():
            base = f"http://127.0.0.1:{port}"
            end = time.time() + 20
            while time.time() < end and not seen.get("done"):
                try:
                    s = json.load(urllib.request.urlopen(base + "/api/starting", timeout=2))
                    if s.get("phase") == "journals":
                        seen["starting"] = s
                        seen["version"] = json.load(urllib.request.urlopen(base + "/api/version", timeout=2))
                        try:
                            urllib.request.urlopen(base + "/api/nearby", timeout=2)
                        except urllib.error.HTTPError as e:
                            seen["nearby"] = (e.code, json.load(e))
                        seen["done"] = True
                except (OSError, ValueError):
                    time.sleep(0.02)
        t = threading.Thread(target=browser, daemon=True)
        t.start()
        out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with unittest.mock.patch.object(ed_outrider, "Starting", Recorded), \
                unittest.mock.patch.object(ed_outrider.Journals, "import_steps", slow_steps), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            ed_outrider.main(["--config", cfg, "--db", os.path.join(self.tmp.name, "x.sqlite"), "--port", str(port),
                              "--host", "127.0.0.1", "--journals", jdir])
        t.join(5)
        out.seek(0)
        log = out.read()
        self.assertTrue(seen.get("done"), log)
        self.assertEqual(seen["starting"]["text"][:len("Reading your journals: March 2024, ")],
                         "Reading your journals: March 2024, ")
        self.assertEqual(seen["version"]["outrider"], outrider.__version__)
        self.assertEqual((seen["nearby"][0], seen["nearby"][1]["code"]), (503, "starting"))
        self.assertIn("stopped during start-up (the journals not read yet are read at the next start)", log)
        self.assertNotIn("serving on", log)
        self.assertTrue(ed_outrider.port_free("127.0.0.1", port))   # the starting app let the port go


    def test_a_database_that_cannot_be_opened_says_what_to_do(self):
        """Review 2026-10-23 S4-S2: a damaged database ended the start with a traceback and the starting page going
        "not reachable"; it says what to do (the restore command), there and on the page, and exits 1."""
        import socket
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cfg = os.path.join(self.tmp.name, "scratch.toml")
        with open(cfg, "w", encoding="utf-8") as f:
            f.write(f'[server]\nbackup_dir = "{self.tmp.name}/backups"\nbackup_every_days = 0\n'
                    f'[spansh]\nwatch_firsts = false\n[speech]\nserver_player = "off"\n')
        db = os.path.join(self.tmp.name, "broken.sqlite")
        with open(db, "wb") as f:
            f.write(b"this is not a database" * 400)
        made = []

        class Recorded(ed_outrider.Starting):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                made.append(self)
        out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with unittest.mock.patch.object(ed_outrider, "Starting", Recorded), \
                unittest.mock.patch.object(ed_outrider, "STARTING_FAILED_SHOW_S", 0.2), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), self.assertRaises(SystemExit) as e:
            ed_outrider.main(["--config", cfg, "--db", db, "--port", str(port), "--host", "127.0.0.1",
                              "--journals", self.tmp.name])
        out.seek(0)
        log = out.read()
        self.assertEqual(e.exception.code, 1)
        self.assertRegex(log, r"cannot start: +The database .* cannot be opened")
        self.assertIn("--restore", log)
        self.assertNotIn("Traceback", log)
        self.assertEqual((made[0].phase, made[0].info()["text"]), ("failed", "ED Outrider could not start"))
        self.assertIn("--restore", made[0].info()["why"])
        self.assertTrue(ed_outrider.port_free("127.0.0.1", port))   # the starting app let the port go

    def test_a_host_no_longer_this_pcs_falls_back_to_this_pc(self):
        """Review 2026-10-23 S9-S24: [server] host set to a LAN address DHCP has since changed made every start fail (a
        silent crash loop under the service, no page to fix it from): it listens on 127.0.0.1 with a notice instead. A
        port in use still stops it. (A damaged database ends this start right after: no server is run.)"""
        import socket
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cfg = os.path.join(self.tmp.name, "scratch.toml")
        with open(cfg, "w", encoding="utf-8") as f:
            f.write(f'[server]\nbackup_dir = "{self.tmp.name}/backups"\nbackup_every_days = 0\n[spansh]\nwatch_firsts = false\n')
        db = os.path.join(self.tmp.name, "broken.sqlite")
        with open(db, "wb") as f:
            f.write(b"this is not a database" * 400)
        real = ed_outrider.listen_problem
        gone = lambda h, p: (f'cannot listen on {h}:{p}: Cannot assign requested address (is [server] host this machine\'s '
                             'address or name? ...)') if h == "192.168.1.250" else real(h, p)
        out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with unittest.mock.patch.object(ed_outrider, "listen_problem", gone), \
                unittest.mock.patch.object(ed_outrider, "STARTING_FAILED_SHOW_S", 0.1), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), self.assertRaises(SystemExit):
            ed_outrider.main(["--config", cfg, "--db", db, "--port", str(port), "--host", "192.168.1.250",
                              "--journals", self.tmp.name])
        out.seek(0)
        log = out.read()
        self.assertIn("listening on 127.0.0.1 only", log)
        self.assertIn(f"http://127.0.0.1:{port}/", log)                  # the starting page came up on this PC
        self.assertEqual([n["key"] for n in ed_outrider.outrider.notices.BOARD.active()], ["host_fallback"])

if __name__ == "__main__":
    unittest.main()
