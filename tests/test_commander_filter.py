"""The commander filter (the full Fable review of 2026-10-23, S9-S4): [journals] commander reads one commander's journal
files only; another commander playing stands the live layer down; a second FID in the folder gets a card. Every journal
is written into a scratch folder; no real config is touched."""
import json
import os
import shutil
import tempfile
import types
import unittest
import unittest.mock

from support import ed_outrider
import outrider.config_edit  # noqa: E402


def header(ts):
    return {"timestamp": ts, "event": "Fileheader", "part": 1, "gameversion": "4.2.0.100", "build": "r1 "}


def commander(ts, fid, name):
    return {"timestamp": ts, "event": "Commander", "FID": fid, "Name": name}


def jump(ts, name, addr, x=0.0):
    return {"timestamp": ts, "event": "FSDJump", "StarSystem": name, "SystemAddress": addr, "StarPos": [x, 0.0, 0.0]}


class CommanderFilter(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, name, *events, mode="w"):
        with open(os.path.join(self.dir, name), mode, encoding="utf-8", newline="") as f:
            for e in events:
                f.write(json.dumps(e, separators=(", ", ":")) + "\r\n")   # as the game writes it

    def two_commanders(self):
        self.write("Journal.2026-10-01T100000.01.log", header("2026-10-01T10:00:00Z"), commander("2026-10-01T10:00:01Z", "F1", "Alpha"),
                   jump("2026-10-01T10:05:00Z", "Mine One", 1))
        self.write("Journal.2026-10-02T100000.01.log", header("2026-10-02T10:00:00Z"), commander("2026-10-02T10:00:01Z", "F2", "Beta"),
                   jump("2026-10-02T10:05:00Z", "Theirs", 2, x=5))
        self.write("Journal.2026-10-03T100000.01.log", header("2026-10-03T10:00:00Z"), commander("2026-10-03T10:00:01Z", "F1", "Alpha"),
                   jump("2026-10-03T10:05:00Z", "Mine Two", 3, x=9))

    def visited(self):
        return sorted(r[0] for r in self.db.execute("SELECT name FROM visits"))

    def test_the_filter_reads_one_commanders_files(self):
        self.two_commanders()
        self.j.commander_filter = "alpha"   # the name as shown, any case (or the FID)
        self.j.scan_dir(self.dir, upload="catchup")
        self.assertEqual(self.visited(), ["Mine One", "Mine Two"])
        self.assertIsNone(self.j.other_playing)   # the newest file is Alpha's
        # the skipped file is read to its end: nothing of it handled on the next scan either
        self.j.scan_dir(self.dir, upload="live")
        self.assertEqual(self.visited(), ["Mine One", "Mine Two"])
        self.assertEqual(ed_outrider.commander_matches("F2", ("F2", "Beta")), True)
        self.assertEqual(ed_outrider.commander_matches("", ("F2", "Beta")), True)
        self.assertEqual(ed_outrider.commander_matches("Alpha", ("F2", "Beta")), False)

    def test_no_filter_reads_everyone(self):
        self.two_commanders()
        self.j.scan_dir(self.dir, upload="catchup")
        self.assertEqual(self.visited(), ["Mine One", "Mine Two", "Theirs"])

    def test_a_new_live_file_waits_for_its_commander_line(self):
        self.two_commanders()
        self.j.commander_filter = "F1"
        self.j.scan_dir(self.dir, upload="catchup")
        name = "Journal.2026-10-04T100000.01.log"
        self.write(name, header("2026-10-04T10:00:00Z"))
        self.j.scan_dir(self.dir, upload="live")
        self.assertEqual(self.j.offsets.get(os.path.join(self.dir, name), 0), 0)   # nothing read yet
        self.write(name, commander("2026-10-04T10:00:01Z", "F1", "Alpha"), jump("2026-10-04T10:05:00Z", "Mine Three", 4), mode="a")
        self.j.scan_dir(self.dir, upload="live")
        self.assertIn("Mine Three", self.visited())

    def test_an_older_file_cut_before_its_commander_line_is_read(self):
        self.write("Journal.2026-10-01T100000.01.log", header("2026-10-01T10:00:00Z"), jump("2026-10-01T10:05:00Z", "Crashed", 7))
        self.write("Journal.2026-10-02T100000.01.log", header("2026-10-02T10:00:00Z"), commander("2026-10-02T10:00:01Z", "F1", "Alpha"))
        self.j.commander_filter = "F1"
        self.j.scan_dir(self.dir, upload="catchup")
        self.assertEqual(self.visited(), ["Crashed"])

    def test_another_commander_playing_stands_the_live_layer_down(self):
        self.two_commanders()
        self.j.commander_filter = "F1"
        self.j.scan_dir(self.dir, upload="catchup")
        self.write("Journal.2026-10-05T100000.01.log", header("2026-10-05T10:00:00Z"), commander("2026-10-05T10:00:01Z", "F2", "Beta"))
        self.j.scan_dir(self.dir, upload="live")
        self.assertEqual(self.j.other_playing, "Beta")
        with open(os.path.join(self.dir, "Status.json"), "w", encoding="utf-8") as f:
            json.dump({"timestamp": "2026-10-05T10:01:00Z", "event": "Status", "Flags": 16777240, "Fuel": {"FuelMain": 8, "FuelReservoir": 0.5}}, f)
        self.j.read_status(self.dir)
        self.assertIsNone(self.j.status_json)                        # Beta's gauge is not taken for Alpha's
        self.state.commander_notices()
        self.assertIn("CMDR Beta is playing: not tracked here", [n["text"] for n in self.state.notices.active()][0])
        self.state.targeter = types.SimpleNamespace(available=True)   # a fake: the guard comes before any key
        self.assertEqual(self.state.start_autotarget_run("next"), ({"error": "CMDR Beta is playing: not tracked here"}, 409))
        self.state.targeter = None
        self.write("Journal.2026-10-05T120000.01.log", header("2026-10-05T12:00:00Z"), commander("2026-10-05T12:00:01Z", "F1", "Alpha"))
        self.j.scan_dir(self.dir, upload="live")
        self.assertIsNone(self.j.other_playing)                      # Alpha again: back on
        self.state.commander_notices()
        self.assertFalse([n for n in self.state.notices.active() if n["key"] == "commander_other"])

    def test_the_card_for_a_second_commander(self):
        self.two_commanders()
        self.j.scan_dir(self.dir, upload="catchup")
        self.assertEqual({f: e["files"] for f, e in self.j.cmdrs_seen.items()}, {"F1": 2, "F2": 1})
        self.state.commander_notices()
        [card] = [n for n in self.state.notices.active() if n["key"] == "commander_more"]
        self.assertEqual(card["action"], "commander:keep")
        self.assertIn("also logs CMDR Beta (since 2026-10-02), beside CMDR Alpha", card["text"])
        self.assertEqual(self.state.commander_choice()[0]["fid"], "F1")   # the most journals
        self.j.commander_filter = "F1"                                   # set: no card
        self.state.commander_notices()
        self.assertFalse([n for n in self.state.notices.active() if n["key"] == "commander_more"])

    def test_a_single_commander_gets_no_card(self):
        self.write("Journal.2026-10-01T100000.01.log", header("2026-10-01T10:00:00Z"), commander("2026-10-01T10:00:01Z", "F1", "Alpha"))
        self.j.scan_dir(self.dir, upload="catchup")
        self.state.commander_notices()
        self.assertEqual(self.state.notices.active(), [])

    def test_setting_it_writes_the_config(self):
        self.two_commanders()
        self.j.scan_dir(self.dir, upload="catchup")
        self.state.config_path = os.path.join(self.dir, "ed_outrider.toml")
        self.assertEqual(self.state.set_commander_filter("F9")[1], 400)   # not a commander the journals named
        out, status = self.state.set_commander_filter("F2")
        self.assertEqual((status, out["commander"]), (200, "Beta"))
        self.assertIn("restart Outrider", out["note"])                   # no running server here to restart
        with open(self.state.config_path, encoding="utf-8") as f:
            self.assertIn('commander = "Beta"', f.read())

    # ---- the Fable bug check of 2026-10-24, batch 3 ----

    def continued(self, name, ts, *events):
        self.write(name, {"timestamp": ts, "event": "Fileheader", "part": 2, "gameversion": "4.2.0.100", "build": "r1 "}, *events)

    def test_a_continuation_file_is_its_first_parts(self):
        """#12: part 2 of a long session carries no Commander line: it is its first part's, read when that is the
        filter's commander, skipped when not, and it says who plays."""
        self.two_commanders()   # the newest: Alpha's of 10-03
        self.continued("Journal.2026-10-03T100000.02.log", "2026-10-03T14:00:00Z", jump("2026-10-03T14:05:00Z", "Mine Later", 30))
        self.j.commander_filter = "F1"
        self.j.scan_dir(self.dir, upload="catchup")
        self.assertIn("Mine Later", self.visited())
        self.write("Journal.2026-10-04T100000.01.log", header("2026-10-04T10:00:00Z"), commander("2026-10-04T10:00:01Z", "F2", "Beta"))
        self.continued("Journal.2026-10-04T100000.02.log", "2026-10-04T14:00:00Z", jump("2026-10-04T14:05:00Z", "Theirs Later", 31))
        self.j.scan_dir(self.dir, upload="live")
        self.assertNotIn("Theirs Later", self.visited())
        self.assertEqual(self.j.other_playing, "Beta")

    def test_the_stand_down_leaves_the_shared_files_alone(self):
        """#13: while another commander plays, their NavRoute.json, Cargo.json and ShipLocker.json are not read; once
        yours plays again they are."""
        import contextlib
        import io
        self.two_commanders()
        self.j.commander_filter = "F1"
        self.write("Journal.2026-10-05T100000.01.log", header("2026-10-05T10:00:00Z"), commander("2026-10-05T10:00:01Z", "F2", "Beta"))
        read = []
        for name in ("read_navroute", "read_cargo_file", "read_locker_file"):
            setattr(self.j, name, (lambda n: lambda d: read.append(n) or False)(name))
        for fname in ("NavRoute.json", "Cargo.json", "ShipLocker.json"):
            with open(os.path.join(self.dir, fname), "w", encoding="utf-8") as f:
                f.write("{}")
        mtimes = {}
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [self.dir]), contextlib.redirect_stderr(io.StringIO()), \
                unittest.mock.patch.object(self.state, "maybe_unsold", lambda: None):
            self.state.tick(mtimes)
            self.assertEqual((self.j.other_playing, read), ("Beta", []))
            self.write("Journal.2026-10-05T120000.01.log", header("2026-10-05T12:00:00Z"), commander("2026-10-05T12:00:01Z", "F1", "Alpha"))
            self.state.tick(mtimes)   # Alpha again: the files are read
            self.state.tick(mtimes)
        self.assertEqual(sorted(set(read)), ["read_cargo_file", "read_locker_file", "read_navroute"])

    def test_another_commanders_lines_touch_the_estimate_not_the_journal_time(self):
        """#14: an alt's sale re-runs the unsold estimate (it reads every commander); #15: their lines do not move
        last_event_ts."""
        self.write("Journal.2026-10-01T100000.01.log", header("2026-10-01T10:00:00Z"), commander("2026-10-01T10:00:01Z", "F1", "Alpha"))
        self.write("Journal.2026-10-02T100000.01.log", header("2026-10-02T10:00:00Z"), commander("2026-10-02T10:00:01Z", "F2", "Beta"),
                   {"timestamp": "2026-10-02T11:00:00Z", "event": "SellExplorationData", "Systems": ["X"], "BaseValue": 100,
                    "Bonus": 0, "TotalEarnings": 100})
        self.j.commander_filter = "F1"
        self.j.unsold_touched = False
        self.j.scan_dir(self.dir, upload="catchup")
        self.assertTrue(self.j.unsold_touched)
        self.assertLess(self.j.last_event_ts or "", "2026-10-02")

    def test_the_filter_moves_to_a_commander_known_only_by_their_files(self):
        """#16: after a filtered re-read only the filter's commander is noted; the other is still known by the files."""
        self.two_commanders()
        self.j.commander_filter = "F1"
        self.j.scan_dir(self.dir, upload="catchup")
        self.assertNotIn("F2", self.j.cmdrs_seen)
        self.state.config_path = os.path.join(self.dir, "ed_outrider.toml")
        out, status = self.state.set_commander_filter("Beta")
        self.assertEqual((status, out["commander"]), (200, "Beta"))

    def test_two_live_folders_judge_who_plays_by_the_newest_file(self):
        """#17: Beta plays in one live folder; the other folder's newest is an older one of Alpha's."""
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other)
        self.write("Journal.2026-10-05T100000.01.log", header("2026-10-05T10:00:00Z"), commander("2026-10-05T10:00:01Z", "F2", "Beta"))
        with open(os.path.join(other, "Journal.2026-10-01T100000.01.log"), "w", encoding="utf-8", newline="") as f:
            for e in (header("2026-10-01T10:00:00Z"), commander("2026-10-01T10:00:01Z", "F1", "Alpha")):
                f.write(json.dumps(e, separators=(", ", ":")) + "\r\n")
        self.j.commander_filter = "F1"
        for _ in range(2):
            self.j.scan_dir(self.dir, upload="live")
            self.j.scan_dir(other, upload="live")
            self.assertEqual(self.j.other_playing, "Beta")

    def test_the_key_in_the_config_and_the_server_list(self):
        st = ed_outrider.settings_from({"journals": {"commander": " Alpha "}}, types.SimpleNamespace(
            journals=None, legacy=None, host=None, port=None, radius=None, db=None))
        self.assertEqual(st["commander"], "Alpha")
        self.assertIn('commander = "Alpha"', ed_outrider.config_text(st))
        files = dict((g[0], g[2]) for g in outrider.config_edit.GROUPS)["files"]
        self.assertIn(("journals", "commander"), files)
        self.assertIn("CMDR Alpha only -> every commander", ed_outrider.filter_message("Alpha", ""))


if __name__ == "__main__":
    unittest.main()
