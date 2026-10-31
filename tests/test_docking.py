"""#3 (Kurbo26, GitHub discussion #3): docking help. The pad a station gives you (said every time, big on Now and in the
overlay's Target panel) and why one refused, only when that is not obvious. Live only: a re-read says and keeps nothing."""
import time
import types
import unittest

from support import ed_outrider  # also puts the repository root on sys.path

import outrider.overlay  # noqa: E402


def ts(offset=0.0):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + offset))


class Docking(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)

    def ev(self, name, offset=0.0, **kw):
        self.j.handle(dict({"timestamp": ts(offset), "event": name}, **kw))

    def say(self):
        """Let the held grant be said (GRANT_SAY_DELAY_S after it, or the docking computer's wait)."""
        return self.state.docking_release(time.time() + 60)

    def moments(self):
        return [(m["what"], m.get("pad"), m.get("words")) for m in self.j.moments if m["kind"] == "docking"]

    def test_the_events_are_read(self):
        wanted = b"".join(ed_outrider.WANTED)
        for name in ed_outrider.DOCKING_EVENTS:
            self.assertIn(f'"event":"{name}"'.encode(), wanted)

    def test_granted_then_docked(self):
        self.ev("DockingGranted", -5, LandingPad=34, StationName="Jameson Memorial", StationType="Orbis", MarketID=128666762)
        d = self.state.docking_summary()
        self.assertEqual((d["pad"], d["station"], d["type"]), (34, "Jameson Memorial", "Orbis"))
        self.assertEqual(self.state.payload()["docking"]["pad"], 34)
        self.assertEqual(self.moments(), [])   # shown at once, said after the station's own voice
        self.assertTrue(self.say())
        self.assertEqual(self.moments(), [("granted", 34, None)])
        self.ev("Docked", -1, StationName="Jameson Memorial", StationType="Orbis", MarketID=128666762)
        self.assertIsNone(self.state.docking_summary())
        self.assertEqual(self.moments()[-1][0], "clear")

    def test_a_carrier_pad_too_and_the_end_of_it(self):
        """Every grant is said, your own carrier's included (the author); a cancel, a timeout or leaving ends it."""
        for end in ("DockingCancelled", "DockingTimeout", "SupercruiseEntry", "FSDJump"):
            self.ev("DockingGranted", -5, LandingPad=7, StationName="G0X-85Z", StationType="FleetCarrier")
            self.assertEqual(self.state.docking_summary()["pad"], 7)
            self.say()
            self.ev(end, -1, StationName="G0X-85Z")
            self.assertIsNone(self.state.docking_summary(), end)
        self.assertEqual([m[0] for m in self.moments()], ["granted", "clear"] * 4)

    def test_denied_only_when_not_obvious(self):
        self.ev("DockingDenied", -3, Reason="NoSpace", StationName="Jameson Memorial", StationType="Orbis")
        d = self.state.docking_summary()
        self.assertEqual((d["denied"], d["words"]), ("NoSpace", "no pad free for your ship: try again shortly"))
        self.assertEqual(self.moments(), [("denied", None, "no pad free for your ship: try again shortly")])
        # too far: you can see it, the game says so: nothing said, the refusal before it cleared
        self.ev("DockingDenied", -2, Reason="Distance", StationName="Jameson Memorial")
        self.assertIsNone(self.state.docking_summary())
        self.assertEqual([m[0] for m in self.moments()], ["denied", "clear"])
        for reason in ("TooLarge", "RestrictedAccess", "Hostile", "Offences", "ActiveFighter"):
            self.assertIn(reason, ed_outrider.DENIED_WORDS)

    def test_how_long_it_shows(self):
        self.ev("DockingDenied", -3, Reason="TooLarge", StationName="Outpost")
        now = time.time()
        self.assertIsNotNone(self.state.docking_summary(now))
        self.assertIsNone(self.state.docking_summary(now + ed_outrider.DOCK_DENIED_KEEP_S + 5))
        self.ev("DockingGranted", -2, LandingPad=2, StationName="Outpost")
        self.assertIsNotNone(self.state.docking_summary(now + ed_outrider.DOCK_DENIED_KEEP_S + 5))
        self.assertIsNone(self.state.docking_summary(now + ed_outrider.DOCK_GRANT_KEEP_S + 5))
        self.j.status_json = {"flags": ed_outrider.FLAG_DOCKED, "live": True}   # docked: gone whatever the journal said
        self.assertIsNone(self.state.docking_summary(now))

    def test_old_lines_say_and_keep_nothing(self):
        """A re-read, a late legacy folder: no pad said, nothing kept."""
        self.ev("DockingGranted", -86400, LandingPad=12, StationName="Old Station")
        self.ev("DockingDenied", -86000, Reason="NoSpace", StationName="Old Station")
        self.assertIsNone(self.state.docking_summary())
        self.assertEqual(self.moments(), [])
        self.assertIsNone(ed_outrider.meta_get(self.db, "docking"))

    def test_where_the_pad_is(self):
        """#12: a starport or carrier grant carries the place in words and the diagram's map; an outpost the number only."""
        self.ev("DockingGranted", -5, LandingPad=34, StationName="Jameson Memorial", StationType="Orbis")
        d = self.state.docking_summary()
        self.assertEqual((d["layout"], d["where"], d["map"]["kind"], d["map"]["pad"]),
                         ("starport", "at the back · up on your right", "starport", 34))
        self.say()
        m = [x for x in self.j.moments if x["kind"] == "docking"][-1]
        self.assertEqual((m["where"], m["say_where"]),
                         ("at the back · up on your right",
                          "With the green lights on your right, it's at the back, up on your right."))
        self.ev("DockingGranted", -4, LandingPad=7, StationName="G0X-85Z", StationType="FleetCarrier")
        self.assertEqual(self.state.docking_summary()["where"], "port side, toward the bow")
        self.ev("DockingGranted", -3, LandingPad=2, StationName="Outpost", StationType="Outpost")
        d = self.state.docking_summary()
        self.assertEqual((d["pad"], d["where"], d["map"]), (2, None, None))
        self.say()
        self.assertIsNone([x for x in self.j.moments if x["kind"] == "docking"][-1]["say_where"])

    def test_the_green_lights_now_and_then(self):
        """Said at the first starport docking of a session, then every 4th grant; a new session starts again."""
        def said():
            return [x["say_where"].startswith("With the green") for x in self.j.moments
                    if x["kind"] == "docking" and x["what"] == "granted"]
        for k in range(6):
            self.ev("DockingGranted", -20 + k, LandingPad=34, StationName="Jameson Memorial", StationType="Orbis")
            self.say()
        self.assertEqual(said(), [True, False, False, False, True, False])
        self.ev("LoadGame", -10, Commander="Sample Pilot")
        self.ev("DockingGranted", -5, LandingPad=34, StationName="Jameson Memorial", StationType="Orbis")
        self.say()
        self.assertEqual(said()[-1], True)

    def test_the_plugins_test_commands(self):
        """"!sppad 34" typed in game: as a grant at a test starport; other chat is never read or kept."""
        self.ev("SendText", -5, To="local", Message="o7 commanders", Sent=True)
        self.assertIsNone(ed_outrider.meta_get(self.db, "docking"))
        self.ev("SendText", -4, To="local", Message="!sppad 34", Sent=True)
        d = self.state.docking_summary()
        self.assertEqual((d["pad"], d["station"], d["layout"], d["test"]), (34, "Test starport", "starport", True))
        self.ev("SendText", -3, To="local", Message="!scpad 23", Sent=True)
        self.assertEqual(self.state.docking_summary()["where"], "port deck, port side, toward the bow")

    def test_the_diagram_switch(self):
        """[overlay] pad_diagram off: the words stay, no map for the page or the overlay; the switch is a setting."""
        self.ev("DockingGranted", -5, LandingPad=34, StationName="Jameson Memorial", StationType="Orbis")
        self.assertIsNotNone(self.state.docking_shown()["map"])
        out, status = self.state.overlay_set({"pad_diagram": False})
        self.assertEqual(status, 200, out)
        d = self.state.docking_shown()
        self.assertEqual((d["where"], d["map"]), ("at the back · up on your right", None))
        self.assertIsNotNone(self.state.docking_summary()["map"])   # kept, only not shown
        self.assertFalse(self.state.overlay_info()["pad_diagram"])
        self.assertTrue(outrider.overlay.overlay_settings({})["overlay"]["pad_diagram"])   # on by default
        self.assertFalse(outrider.overlay.overlay_settings({"overlay": {"pad_diagram": False}})["overlay"]["pad_diagram"])

    def test_the_overlay_draws_the_diagram(self):
        pal = outrider.overlay.palette("default")
        import outrider.pads as P
        for kind, n in (("starport", 34), ("fleet", 7), ("squadron", 23)):
            w = P.where(kind, n)
            with_map = outrider.overlay.pad_panel({"pad": n, "station": "X", "where": w["words"], "map": w["map"]}, pal)
            words_only = outrider.overlay.pad_panel({"pad": n, "station": "X", "where": w["words"], "map": None}, pal)
            self.assertGreater(len(with_map["items"]), len(words_only["items"]) + 10, kind)
            self.assertGreater(with_map["h"], words_only["h"] + 150, kind)
            said = " ".join(" ".join(r[0] for it in words_only["items"] if it["t"] == "runs" for r in it["runs"]).split())
            self.assertIn(w["words"].split(" · ")[0], said, kind)
            if kind == "starport":   # the slot's lights: green on the right of the far wall, red on the left
                lights = [it for it in with_map["items"] if it["t"] == "line" and it["c"] in ("#3AD16B", "#E0453A")]
                green = next(it for it in lights if it["c"] == "#3AD16B")
                red = next(it for it in lights if it["c"] == "#E0453A")
                self.assertGreater(green["pts"][1][0], red["pts"][0][0])

    def fit(self, *items):
        self.ev("Loadout", -60, Ship="krait_light", ShipID=7, ShipName="Sample Ship", ShipIdent="SP-01", UnladenMass=400.0,
                FuelCapacity={"Main": 32.0, "Reserve": 0.63}, MaxJumpRange=40.0,
                Modules=[{"Slot": f"Slot0{i}_Size2", "Item": it, "Health": 1.0} for i, it in enumerate(items, 1)])

    def granted(self):
        return [m for m in self.j.moments if m["kind"] == "docking" and m["what"] == "granted"]

    def test_quiet_when_the_docking_computer_takes_over(self):
        """#12 (the author): with a docking computer fitted, the pad shows at once but is said only if the computer has
        not taken over (its Music line) within AUTO_DOCK_WAIT_S."""
        self.fit("int_dockingcomputer_advanced")
        self.assertTrue(self.j.docking_computer())
        self.ev("DockingGranted", -8, LandingPad=34, StationName="Jameson Memorial", StationType="Orbis")
        self.assertEqual(self.state.docking_summary()["pad"], 34)   # shown at once
        self.assertEqual(self.granted(), [])                        # not said yet
        self.ev("Music", -5, MusicTrack="DockingComputer")
        self.assertFalse(self.state.docking_release(time.time() + 60))
        self.assertEqual(self.granted(), [])                        # never said
        self.assertEqual(self.state.docking_summary()["pad"], 34)   # still shown

    def test_said_late_when_flown_by_hand(self):
        """The docking computer fitted but not taking over (switched off): said once the wait is over, never twice."""
        self.fit("int_dockingcomputer_standard")
        self.ev("DockingGranted", -2, LandingPad=7, StationName="G0X-85Z", StationType="FleetCarrier")
        self.ev("Music", -1, MusicTrack="Starport")   # another track: not the computer
        self.assertFalse(self.state.docking_release(time.time()))
        self.assertTrue(self.state.docking_release(time.time() + ed_outrider.AUTO_DOCK_WAIT_S))
        self.assertFalse(self.state.docking_release(time.time() + 60))
        self.assertEqual([(m["pad"], m["say_where"]) for m in self.granted()], [(7, "Port side, toward the bow.")])

    def test_said_after_the_station_without_a_docking_computer(self):
        """No docking computer: said GRANT_SAY_DELAY_S after the grant, not over the station's own voice (Kurbo26)."""
        self.fit("int_fuelscoop_size5_class5")
        self.assertFalse(self.j.docking_computer())
        self.ev("DockingGranted", -2, LandingPad=7, StationName="G0X-85Z", StationType="FleetCarrier")
        self.assertEqual(len(self.granted()), 0)
        self.assertFalse(self.state.docking_release(time.time()))                                    # 2 s after it
        self.assertTrue(self.state.docking_release(time.time() - 2 + ed_outrider.GRANT_SAY_DELAY_S))  # its 5 s
        self.assertEqual(len(self.granted()), 1)
        self.fit("int_dockingcomputer_advanced")
        self.ev("SendText", -1, To="local", Message="!sppad 3", Sent=True)   # a test: said at once whatever is fitted
        self.assertEqual(len(self.granted()), 2)

    def test_the_delay_is_a_setting(self):
        """[speech] pad_delay (Kurbo26, 2026-10-15: some stations' controllers talk for up to 13 s): read and kept to 0-20 s,
        5 unset; the next grant waits that long (the docking computer's wait is its own)."""
        args = types.SimpleNamespace(**{k: None for k in ("journals", "legacy", "host", "port", "db", "radius")})
        read = lambda spk: ed_outrider.settings_from({"speech": spk}, args)["pad_delay"]
        self.assertEqual([read({}), read({"pad_delay": 12}), read({"pad_delay": 99}), read({"pad_delay": -3})], [5, 12, 20, 0])
        self.assertIn("pad_delay = 12", ed_outrider.config_text(ed_outrider.settings_from({"speech": {"pad_delay": 12}}, args)))
        self.fit("int_fuelscoop_size5_class5")
        self.j.pad_delay = 12
        self.ev("DockingGranted", -2, LandingPad=7, StationName="G0X-85Z", StationType="FleetCarrier")
        self.assertFalse(self.state.docking_release(time.time() - 2 + 6))    # the old 5 s: not yet
        self.assertTrue(self.state.docking_release(time.time() - 2 + 12))
        self.j.pad_delay = 0
        self.ev("DockingGranted", -1, LandingPad=8, StationName="G0X-85Z", StationType="FleetCarrier")
        self.assertTrue(self.state.docking_release(time.time()))              # 0: at once

    def test_a_held_grant_wakes_the_page(self, computer=False):
        """Kurbo26, 2026-10-26: with pad_delay at 9 s the overlay showed the pad at once (it asks every second) but Now and
        the tablet's switch to it waited for the voice: a tick that reads only a held grant bumps the long poll.
        computer: a docking computer fitted, its Music line read in the same tick (review 8): the hold set and gone
        again, the pad still shown."""
        import json
        import os
        import tempfile
        import unittest.mock
        self.fit("int_dockingcomputer_advanced" if computer else "int_fuelscoop_size5_class5")
        self.j.pad_delay = 9
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        later = ("watch_status", "maybe_refresh", "apply_own_changes", "maybe_classify_target", "maybe_unsold",
                 "maybe_sale_left", "maybe_locate_carrier", "maybe_find_sellers", "maybe_backup_on_quit")
        with unittest.mock.patch.object(ed_outrider, "LIVE_DIRS", [d]):
            patches = [unittest.mock.patch.object(self.state, n, lambda *a: None) for n in later]
            for p in patches:
                p.start()
            try:
                self.state.tick({})
                v = self.state.version
                with open(os.path.join(d, "Journal.2026-10-27T120000.01.log"), "w") as f:
                    f.write(json.dumps({"timestamp": ts(-1), "event": "DockingGranted", "LandingPad": 34,
                                        "StationName": "Jameson Memorial", "StationType": "Orbis"},
                                       separators=(",", ":")) + "\n")   # as the game writes it
                    if computer:
                        f.write(json.dumps({"timestamp": ts(-1), "event": "Music", "MusicTrack": "DockingComputer"},
                                           separators=(",", ":")) + "\n")
                self.state.tick({})
            finally:
                for p in patches:
                    p.stop()
        if computer:
            self.assertIsNone(self.j.docking_hold)   # the docking computer took over: never said
        else:
            self.assertIsNotNone(self.j.docking_hold)
        self.assertEqual(self.granted(), [])                       # not said yet
        self.assertEqual(self.state.payload()["docking"]["pad"], 34)
        self.assertGreater(self.state.version, v)                  # but the page is told now

    def test_a_grant_and_the_docking_computer_in_one_read(self):
        self.test_a_held_grant_wakes_the_page(computer=True)

    def test_a_dock_or_leaving_drops_the_hold(self):
        self.fit("int_dockingcomputer_advanced")
        self.ev("DockingGranted", -6, LandingPad=34, StationName="Jameson Memorial", StationType="Orbis")
        self.ev("DockingCancelled", -3, StationName="Jameson Memorial")
        self.assertFalse(self.state.docking_release(time.time() + 60))
        self.assertEqual(self.granted(), [])

    def test_a_failed_tick_puts_the_hold_back(self):
        self.fit("int_dockingcomputer_advanced")
        cp = self.j.checkpoint()
        self.ev("DockingGranted", -6, LandingPad=34, StationName="Jameson Memorial", StationType="Orbis")
        self.assertIsNotNone(self.j.docking_hold)
        self.j.restore(cp)
        self.assertIsNone(self.j.docking_hold)

    def test_live_only(self):
        self.assertNotIn("docking", ed_outrider.RESET_JOURNAL_DATA)   # a re-read would drop a grant in progress
        self.ev("DockingGranted", -86400, LandingPad=12, StationName="Old", StationType="Orbis")
        self.assertIsNone(ed_outrider.meta_get(self.db, "docking_said"))   # the cadence counts live grants only

    def test_the_pad_panel(self):
        pal = outrider.overlay.palette("default")
        p = outrider.overlay.pad_panel({"pad": 34, "station": "Jameson Memorial"}, pal)
        texts = [r[0] for it in p["items"] if it["t"] == "runs" for r in it["runs"]]
        self.assertEqual(p["id"], "radar")   # the Surface radar's place, size and switch (the author, 2026-10-14)
        self.assertIn("PAD 34", texts)
        big = next(it for it in p["items"] if it["t"] == "runs" and it["runs"][0][0] == "PAD 34")
        self.assertEqual((big["runs"][0][2], big.get("align")), ("huge", "center"))
        self.assertGreater(outrider.overlay.FONT_PX["huge"], outrider.overlay.FONT_PX["large"] * 2)
        self.assertTrue(any("Jameson Memorial" in t for t in texts))
        no = outrider.overlay.pad_panel({"denied": "NoSpace", "words": "no pad free for your ship: try again shortly",
                                         "station": "Jameson Memorial"}, pal)
        words = " ".join(" ".join(r[0] for it in no["items"] if it["t"] == "runs" for r in it["runs"]).split())
        self.assertIn("Docking denied", words)
        self.assertIn("no pad free", words)
        self.assertIn("try again shortly", words)   # wrapped, never cut with …
        self.assertNotIn("…", words)
        for size in ("small", "normal", "large"):   # the longest reason wraps at every text size
            long = outrider.overlay.pad_panel({"denied": "RestrictedAccess", "station": "X",
                                               "words": ed_outrider.DENIED_WORDS["RestrictedAccess"]}, pal, size)
            said = " ".join(r[0] for it in long["items"] if it["t"] == "runs" for r in it["runs"])
            self.assertNotIn("…", said, size)
        self.assertIsNone(outrider.overlay.pad_panel(None, pal))

    def test_the_radars_place_shows_the_pad_while_docking(self):
        """overlay_panels: while a grant holds, the pad in the Surface radar's place (switched with the radar), the
        Target panel left to the target; never over the galaxy map (the author, 2026-10-14)."""
        self.j.pos = {"id64": 1, "name": "Shinrarta Dezhra", "x": 0, "y": 0, "z": 0, "ts": ts(-60)}
        self.state.overlay_cfg = dict(outrider.overlay.DEFAULTS, enabled=True)
        self.j.status_json = {"live": True, "flags": ed_outrider.FLAG_IN_MAIN_SHIP, "gui_focus": 0, "ts": ts(-1)}
        texts = lambda ps: {p["id"]: [r[0] for it in p["items"] if it["t"] == "runs" for r in it["runs"]] for p in ps}
        self.assertNotIn("radar", texts(self.state.overlay_panels()))   # in space, no grant: the radar has nothing
        self.ev("DockingGranted", -5, LandingPad=34, StationName="Jameson Memorial", StationType="Orbis")
        shown = texts(self.state.overlay_panels())
        self.assertIn("PAD 34", shown["radar"])
        self.assertFalse(any("PAD 34" in t for pid, ts_ in shown.items() if pid != "radar" for t in ts_))
        self.state.overlay_cfg = dict(self.state.overlay_cfg, radar=False)
        self.assertNotIn("radar", texts(self.state.overlay_panels()))   # the radar's switch is the pad's too
        self.state.overlay_cfg = dict(self.state.overlay_cfg, radar=True)
        self.j.status_json = dict(self.j.status_json, gui_focus=ed_outrider.OVERLAY_GALAXY_MAP)
        self.assertNotIn("radar", texts(self.state.overlay_panels()))   # over the galaxy map: the Target panel only


if __name__ == "__main__":
    unittest.main()
