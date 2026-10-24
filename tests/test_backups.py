"""Setup and the server's backups (batch 5 of the held suggestions): the backup before a journal re-read (S4), the
database's lock and Settings -> Server -> Backups with the restore command for this install (S44), and the first run
with no journals (S43). Every backup goes into a scratch folder: never data/backups."""
import asyncio
import contextlib
import io
import json
import os
import sqlite3
import tempfile
import types
import unittest
import unittest.mock

from support import ed_outrider  # also puts the repository root on sys.path

import outrider.auth  # noqa: E402
import outrider.notices as N  # noqa: E402


def journal(folder, name="Journal.2026-10-01T120000.01.log", events=({"event": "Fileheader"},)):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        for i, ev in enumerate(events):
            f.write(json.dumps(dict({"timestamp": f"2026-10-01T12:00:{i:02d}Z"}, **ev), separators=(", ", ":")) + "\n")
    return os.path.join(folder, name)


class Scratch(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp = t.name
        self.dbp = os.path.join(self.tmp, "data", "x.sqlite")
        self.out = os.path.join(self.tmp, "backups")
        os.makedirs(os.path.dirname(self.dbp))

    def used_db(self, visits=2, version=None):
        """A database in use: some journal-derived rows, written by an older journal reader (`version`)."""
        db = ed_outrider.open_db(self.dbp)
        for i in range(visits):
            db.execute("INSERT INTO visits (id64, name, first_ts, last_ts, count) VALUES (?, ?, ?, ?, 1)",
                       (i + 1, f"Sys {i}", "2026-10-01T12:00:00Z", "2026-10-01T12:00:00Z"))
        ed_outrider.meta_set(db, "parser_version", ed_outrider.PARSER_VERSION - 1 if version is None else version)
        db.commit()
        db.close()


class BackupBeforeReread(Scratch):
    """S4: a journal re-read clears the journal-derived tables: the database is backed up first, its zip tagged."""

    def test_the_tagged_name_lists_rotates_and_is_swept(self):
        self.assertEqual(ed_outrider.backup_name("/a/x.sqlite", 0, tag="pre-reread"), "outrider-x-19700101-000000Z-pre-reread.zip")
        os.makedirs(self.out)
        names = ["outrider-x-20260101-000000Z.zip", "outrider-x-20260102-000000Z-pre-reread.zip",
                 "outrider-x-20260103-000000Z.zip", "outrider-x-20260104-000000Z-unknown.zip", "outrider-y-20260105-000000Z-pre-reread.zip"]
        for f in names:
            open(os.path.join(self.out, f), "w").close()
        # the tag after the stamp: in time order with the others (a prefix would sort after all of them for good)
        self.assertEqual(ed_outrider.backup_zips(self.out, self.dbp), names[:3])
        self.assertEqual(ed_outrider.rotate_backups(self.out, 1, self.dbp), 1)
        self.assertEqual(sorted(os.listdir(self.out)), sorted(names[2:]))
        for f in ("outrider-x-20260106-000000Z-pre-reread.zip.part", ".db-outrider-x-20260106-000000Z-pre-reread.sqlite"):
            open(os.path.join(self.out, f), "w").close()
        with contextlib.redirect_stdout(io.StringIO()):
            removed = ed_outrider.sweep_backup_leftovers(self.out, self.dbp)
        self.assertEqual(sorted(removed), [".db-outrider-x-20260106-000000Z-pre-reread.sqlite",
                                           "outrider-x-20260106-000000Z-pre-reread.zip.part"])

    def test_open_db_backs_up_before_any_row_goes(self):
        seen = []

        def before(db):
            seen.append(db.execute("SELECT count(*) FROM visits").fetchone()[0])
        db = ed_outrider.open_db(self.dbp, before_reset=before)   # a new database: nothing to back up
        db.close()
        self.assertEqual(seen, [])
        self.used_db(visits=2)
        db = ed_outrider.open_db(self.dbp, on_reread=lambda why: None, before_reset=before)
        self.addCleanup(db.close)
        self.assertEqual(seen, [2])   # called with the rows still there
        self.assertEqual(db.execute("SELECT count(*) FROM visits").fetchone()[0], 0)
        db.close()
        db = ed_outrider.open_db(self.dbp, before_reset=before)   # the same reader: no re-read, no backup
        db.close()
        db = ed_outrider.open_db(self.dbp, rescan=True, on_reread=lambda why: None, before_reset=before)   # --rescan
        db.close()
        self.assertEqual(seen, [2, 0])
        # a crashed first run (an empty database, no parser version stored): nothing to back up
        os.remove(self.dbp)
        sqlite3.connect(self.dbp).close()
        db = ed_outrider.open_db(self.dbp, rescan=True, on_reread=lambda why: None, before_reset=before)
        db.close()
        self.assertEqual(seen, [2, 0])

    def test_a_tagged_backup_even_with_automatic_backups_off(self):
        self.used_db(visits=3)
        live = os.path.join(self.tmp, "live")
        journal(live)
        speech = os.path.join(self.tmp, "speech.json")
        with open(speech, "w") as f:
            f.write("{}")
        board = N.Board()
        with unittest.mock.patch.object(ed_outrider, "BACKUP_EVERY_DAYS", 0), contextlib.redirect_stdout(io.StringIO()) as out:
            db = ed_outrider.open_db(self.dbp, on_reread=print, before_reset=lambda d: ed_outrider.backup_before_reread(
                d, self.dbp, self.out, 7, ed_outrider.backup_extras(speech, None, None), [live], board))
        self.addCleanup(db.close)
        zips = os.listdir(self.out)
        self.assertEqual(len([z for z in zips if z.endswith("-pre-reread.zip")]), 1, zips)
        self.assertIn("backup before the journal re-read written: ", out.getvalue())
        self.assertEqual(os.listdir(os.path.join(self.out, "journals")), ["Journal.2026-10-01T120000.01.log"])   # archived too
        import zipfile
        name = next(z for z in zips if z.endswith(".zip"))
        with zipfile.ZipFile(os.path.join(self.out, name)) as z:
            self.assertEqual(sorted(z.namelist()), ["speech.json", "x.sqlite"])
            backed = os.path.join(self.tmp, "copy.sqlite")
            with open(backed, "wb") as f:
                f.write(z.read("x.sqlite"))
        con = sqlite3.connect(backed)
        self.assertEqual(con.execute("SELECT count(*) FROM visits").fetchone()[0], 3)   # the rows as they were
        con.close()
        self.assertIsNone(ed_outrider.meta_get(db, "last_backup"))   # the Data tile's line is about the regular ones
        self.assertEqual(db.execute("SELECT count(*) FROM visits").fetchone()[0], 0)   # and the re-read went on
        self.assertEqual(board.active(), [])

    def test_your_own_personalities_go_in_the_zip(self):
        """Review 2026-10-23 S9-S23: the backup carried every other hand-written file but your own personality files
        (data/personalities/, thousands of lines); a shipped one never goes in."""
        speech = os.path.join(self.tmp, "speech.json")
        with open(speech, "w") as f:
            f.write("{}")
        mine = os.path.join(self.tmp, "personalities")
        os.makedirs(mine)
        for n in ("pirate.json", "notes.txt"):
            with open(os.path.join(mine, n), "w") as f:
                f.write("{}")
        extras = ed_outrider.backup_extras(speech, None, None)
        self.assertIn((os.path.join(mine, "pirate.json"), "personalities/pirate.json"), extras)
        self.assertNotIn("personalities/notes.txt", [n for _, n in extras])
        self.assertFalse([n for _, n in extras if "resources" in n])
        self.used_db(visits=1)
        with contextlib.redirect_stdout(io.StringIO()):
            got = ed_outrider.write_backup(self.dbp, self.out, 7, extras)
        self.assertIn("personalities/pirate.json", got["files"])

    def test_a_failed_backup_says_so_and_the_reread_goes_on(self):
        self.used_db(visits=1)
        open(self.out, "w").close()   # the backups folder is a file: nothing can be written there
        board = N.Board()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            db = ed_outrider.open_db(self.dbp, on_reread=print, before_reset=lambda d: ed_outrider.backup_before_reread(
                d, self.dbp, self.out, 7, board=board))
        self.addCleanup(db.close)
        self.assertEqual(db.execute("SELECT count(*) FROM visits").fetchone()[0], 0)
        got = {n["key"]: n for n in board.active()}
        self.assertEqual((got["reread_backup"]["level"], got["reread_backup"]["action"]), ("bad", "open:log"))
        self.assertIn("The backup before the journal re-read failed", got["reread_backup"]["text"])
        self.assertIn("backup before the journal re-read failed", err.getvalue())

    def test_journals_gone_are_said(self):
        """More than half the journal files the database was read from gone (an uninstall under Steam): said, with
        the archive to read them from."""
        kept = journal(os.path.join(self.tmp, "live"))
        gone = [os.path.join(self.tmp, "gone", f"Journal.{i}.log") for i in (1, 2)]
        for paths, said in (([kept, gone[0]], False), ([kept] + gone, True)):   # 1 of 2 gone: not over half; 2 of 3: said
            self.used_db(visits=1)
            db = sqlite3.connect(self.dbp)
            db.execute("DELETE FROM journal_files")
            db.executemany("INSERT INTO journal_files (path, offset) VALUES (?, 10)", [(p,) for p in paths])
            db.commit()
            db.close()
            board = N.Board()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                db = ed_outrider.open_db(self.dbp, before_reset=lambda d: ed_outrider.backup_before_reread(
                    d, self.dbp, self.out, 7, board=board))
            db.close()
            got = {n["key"]: n["text"] for n in board.active()}
            self.assertEqual("reread_journals_gone" in got, said, got)
        self.assertIn("2 of the 3 journal files", got["reread_journals_gone"])
        self.assertIn("--legacy " + os.path.join(self.out, "journals"), got["reread_journals_gone"])


class DatabaseLock(Scratch):
    """S44's lock: <db>.lock held by a running Outrider; --restore refuses WHILE it is held, whatever the port."""

    def test_restore_refuses_while_the_lock_is_held(self):
        self.assertFalse(ed_outrider.db_in_use(self.dbp))
        self.assertFalse(os.path.exists(self.dbp + ".lock"))   # asking never makes the file
        self.used_db(visits=1, version=ed_outrider.PARSER_VERSION)
        os.makedirs(self.out)
        import zipfile
        zp = os.path.join(self.out, "outrider-x-20260101-000000Z.zip")
        with zipfile.ZipFile(zp, "w") as z:
            z.write(self.dbp, "x.sqlite")
        lock = ed_outrider.db_lock(self.dbp)   # as run() holds it
        self.assertIsNotNone(lock)
        try:
            self.assertIsNone(ed_outrider.db_lock(self.dbp))   # a second Outrider cannot take it
            self.assertTrue(ed_outrider.db_in_use(self.dbp))
            with self.assertRaisesRegex(RuntimeError, r"ED Outrider is running with .*x\.sqlite\.lock"):
                ed_outrider.restore_backup(zp, self.dbp, "127.0.0.1", 0)   # port 0: the port check sees nothing
            self.assertFalse([f for f in os.listdir(os.path.dirname(self.dbp)) if "pre-restore" in f])
        finally:
            lock.close()
        self.assertFalse(ed_outrider.db_in_use(self.dbp))   # let go (as when Outrider stops, however it stops)
        lines = ed_outrider.restore_backup(zp, self.dbp, "127.0.0.1", 0)
        self.assertTrue(lines[0].startswith("restored "))


class RestoreCommand(unittest.TestCase):
    """S44: the command that works on each install (install.md says the same)."""

    def test_the_service_is_stopped_and_started_around_it(self):
        """Review 2026-10-23 S9-S22: under the systemd service the command could not work (the unit holds the database)
        and the refusal did not say how to stop it."""
        name = "outrider-ed_outrider-20261001-120000Z.zip"
        self.assertEqual(ed_outrider.restore_command(name, "git", root="/o", service=True),
                         f"systemctl --user stop ed-outrider && cd /o && ./launch_outrider.sh --restore {name} && "
                         "systemctl --user start ed-outrider")
        with unittest.mock.patch.object(ed_outrider, "systemd_service_installed", lambda: True):
            self.assertTrue(ed_outrider.restore_command(None, "download", root="/o").startswith("systemctl --user stop"))
        self.assertFalse(ed_outrider.restore_command(None, "download", root="/o").startswith("systemctl"))

    def test_each_install(self):
        cmd = ed_outrider.restore_command
        name = "outrider-ed_outrider-20261001-120000Z.zip"
        self.assertEqual(cmd(name, "git", root="/home/me/Elite Data"),
                         f"cd '/home/me/Elite Data' && ./launch_outrider.sh --restore {name}")
        self.assertEqual(cmd(None, "download", root="/opt/outrider"), "cd /opt/outrider && ./launch_outrider.sh --restore")
        self.assertEqual(cmd(name, "git", root="/o", extra=["--config", "/my files/o.toml", "--db", "/d/x.sqlite"]),
                         f"cd /o && ./launch_outrider.sh --config '/my files/o.toml' --db /d/x.sqlite --restore {name}")
        self.assertEqual(cmd(name, "download", windows=True, root=r"C:\Games\ED Outrider", extra=["--config", r"C:\o.toml"]),
                         rf'cd /d "C:\Games\ED Outrider" && launch_outrider.bat --config C:\o.toml --restore {name}')
        # Docker: the container stopped first (the port check cannot see it), restored in a one-off one, started again;
        # the entrypoint passes the config, so no extra arguments
        self.assertEqual(cmd(name, "docker", extra=["--config", "/config/ed_outrider.toml"]),
                         f"docker compose stop && docker compose run --rm outrider --restore {name} && docker compose up -d")


class BackupsList(Scratch):
    """S44: GET /api/backups, Settings -> Server -> Backups."""

    def state(self):
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        state = ed_outrider.State(db, ed_outrider.Journals(db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        state.db_path, state.install, state.restore_extra = self.dbp, "git", ("--db", self.dbp)
        return state

    def test_newest_first_with_what_made_each_when_known(self):
        state = self.state()
        os.makedirs(self.out)
        names = ["outrider-x-20260101-000000Z.zip", "outrider-x-20260102-000000Z-pre-reread.zip",
                 "outrider-x-20260103-000000Z.zip", "outrider-other-20260104-000000Z.zip"]
        for i, f in enumerate(names):
            with open(os.path.join(self.out, f), "wb") as fh:
                fh.write(b"z" * (i + 1) * 1000)
        ed_outrider.meta_set(state.db, "last_backup", {"path": os.path.join(self.out, names[2]), "ts": "2026-01-03T00:00:00Z", "auto": True})
        with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", self.out):
            got = state.backup_list()
            self.assertEqual([b["name"] for b in got["backups"]], names[2::-1])   # newest first, this database's only
            self.assertEqual([b["kind"] for b in got["backups"]], ["auto", "pre-reread", None])   # the others: not known
            self.assertEqual(got["backups"][0]["size"], 3000)
            self.assertEqual(got["backups"][1]["command"], state.restore_command(names[1]))
            self.assertIn(f"--db {self.dbp} --restore {names[1]}", got["backups"][1]["command"])
            self.assertEqual((got["folder"], got["install"], got["error"]), (self.out, "git", None))
            ed_outrider.meta_set(state.db, "last_backup", {"path": os.path.join(self.out, names[2]), "auto": False})
            self.assertEqual(state.backup_list()["backups"][0]["kind"], "manual")
            # a failed attempt since: its `auto` is that attempt's, so the latest's kind is not known
            ed_outrider.meta_set(state.db, "last_backup", {"path": os.path.join(self.out, names[2]), "auto": True, "error": "x"})
            self.assertIsNone(state.backup_list()["backups"][0]["kind"])
            out = asyncio.run(self.get(state))
        self.assertEqual([b["name"] for b in out["ok"]["backups"]], names[2::-1])
        self.assertEqual(out["lan"], 401)   # behind the sign-in, as the rest
        with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", os.path.join(self.tmp, "none")):
            self.assertEqual((state.backup_list()["backups"], state.backup_list()["error"]), ([], None))   # none made yet
        # the payload's backup line carries the newest's command for the Data tile's title
        state.install = "docker"
        self.assertEqual(state.payload()["backup"]["restore"],
                         "docker compose stop && docker compose run --rm outrider --restore && docker compose up -d")

    async def get(self, state):
        from aiohttp.test_utils import TestClient, TestServer
        state.password = "hunter2"
        async with TestClient(TestServer(ed_outrider.make_app(state))) as c:
            ok = await (await c.get("/api/backups")).json()
            with unittest.mock.patch.object(outrider.auth, "is_loopback", lambda remote: False):   # another device
                lan = (await c.get("/api/backups")).status
        return {"ok": ok, "lan": lan}


class BackupSpace(Scratch):
    """Review 2026-10-23 S9-S36: a full disk was found only when a backup failed half way (the pre-reread one too); the
    Backups box says what they take and the room left, a backup is refused in words first, a card when it runs low."""

    def test_refused_in_words_and_said(self):
        self.used_db(visits=50)
        size = os.path.getsize(self.dbp)
        with unittest.mock.patch.object(ed_outrider, "disk_free", lambda p: size):   # under 1.2 x the database
            with self.assertRaises(RuntimeError) as e:
                ed_outrider.write_backup(self.dbp, self.out, 7)
        self.assertIn("not enough free space for a backup", str(e.exception))
        self.assertFalse([n for n in os.listdir(self.out) if n.endswith(".zip")])    # nothing written, nothing rotated
        with contextlib.redirect_stdout(io.StringIO()):
            ed_outrider.write_backup(self.dbp, self.out, 7)
        aside = self.dbp + ".pre-restore-20261001-120000"
        with open(aside, "wb") as f:
            f.write(b"x" * 1000)
        sp = ed_outrider.backup_space(self.dbp, self.out)
        self.assertGreater(sp["zips"], 0)
        self.assertEqual((sp["pre_restore"], sp["db"], sp["low"]), ([{"path": aside, "size": 1000}], size, False))
        with unittest.mock.patch.object(ed_outrider, "disk_free", lambda p: size * 2):
            self.assertTrue(ed_outrider.backup_space(self.dbp, self.out)["low"])     # under two backups' worth
            db = ed_outrider.open_db(self.dbp)
            self.addCleanup(db.close)
            st = ed_outrider.State(db, ed_outrider.Journals(db), types.SimpleNamespace(cached=lambda i: (None, None)), 25)
            st.db_path = self.dbp
            with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", self.out):
                st.backup_space_notice()
                self.assertEqual([n["key"] for n in st.notices.active()], ["backup_disk"])
                self.assertIn("space", st.backup_list())
        with unittest.mock.patch.object(ed_outrider, "BACKUP_DIR", self.out):
            st.backup_space_notice()
        self.assertEqual(st.notices.active(), [])                                   # room again: gone


class FirstRunNoJournals(Scratch):
    """S43: no journal read yet: the payload says so (and how this copy runs); the banner's notice goes with the first
    journal."""

    def test_missing_until_a_journal_is_read(self):
        db = ed_outrider.open_db(":memory:")
        self.addCleanup(db.close)
        j = ed_outrider.Journals(db)
        state = ed_outrider.State(db, j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        state.install = "docker"
        fr = state.payload()["freshness"]
        self.assertEqual((fr["missing"], fr["install"]), (True, "docker"))
        live = os.path.join(self.tmp, "live")
        os.makedirs(live)
        state.notices.set("no_journal_files", ed_outrider.DOCKER_NO_JOURNALS)

        async def ticks():   # the tick's follow-ups start tasks: on a loop, as in watch()
            state.tick({})   # an empty folder: still missing
            self.assertEqual([n["key"] for n in state.notices.active()], ["no_journal_files"])
            journal(live, events=({"event": "Fileheader", "part": 1, "gameversion": "4.0", "build": "r1"},))
            state.tick({})
            rest = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]   # the unsold estimate's
            for t in rest:
                t.cancel()
            await asyncio.gather(*rest, return_exceptions=True)
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [live]):
            asyncio.run(ticks())
        self.assertFalse(state.payload()["freshness"]["missing"])
        self.assertEqual(state.notices.active(), [])


if __name__ == "__main__":
    unittest.main()
