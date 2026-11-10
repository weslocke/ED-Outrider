"""Telling you about notable stellar phenomena in a system (project/PLAN-nsp-alert-2026-11-10.md): Canonn's reports as
you arrive ([server] canonn_reports), else your own record of sites not yet dropped at, else the FSS's listing; never
for what you logged there, once a visit. Canonn's answers are the shape of getSystemPoi's (checked 2026-11-10 on the
author's Smojooe XF-G b24-0 and on Aedgorn EW-N d6-1). Fakes only: no network."""
import argparse
import asyncio
import time
import types
import unittest
from unittest import mock

from support import ed_outrider
import outrider.canonn_sites as CS
import outrider.config_edit as CE

SYSTEM, NAME = 44636064571, "Aedgorn EW-N d6-1"
MOLLUSC, CRYSTALS, RUBEUM = 2300101, 2100801, 2100803
BACTERIUM = 2320609            # a surface biology entry: never a phenomenon


def poi(*codex):
    return {"system": NAME, "odyssey": "Y", "cmdrName": None, "codex": list(codex)}


def space(entry, name):
    return {"english_name": name, "entryid": entry, "hud_category": "Cloud", "body": None, "latitude": None}


ANSWER = poi(space(MOLLUSC, "Albulum Gourd Mollusc"), space(CRYSTALS, "Prasinum Metallic Crystals"),
             {"english_name": "Bacterium Alcyoneum - Red", "entryid": BACTERIUM, "hud_category": "Biology", "body": "D 3",
              "latitude": "-53.8"},
             space(MOLLUSC, "Albulum Gourd Mollusc"))   # reported twice: said once


class SpaceEntries(unittest.TestCase):
    def test_space_rows_only(self):
        ids = {MOLLUSC, CRYSTALS, RUBEUM}
        self.assertEqual(CS.space_entries(ANSWER, ids), [MOLLUSC, CRYSTALS])
        self.assertEqual(CS.space_entries(ANSWER, {CRYSTALS}), [CRYSTALS])            # not on the Phenomena list: left out
        self.assertEqual(CS.space_entries(poi(dict(space(RUBEUM, "R"), entryid=str(RUBEUM))), ids), [RUBEUM])   # a string id
        self.assertEqual(CS.space_entries({"system": NAME}, ids), [])                  # nothing reported
        for bad in (None, [], {"error": "busy"}, {"system": NAME, "codex": "x"}):
            with self.assertRaises(ValueError):
                CS.space_entries(bad, ids)


class Arrival(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.asked = []

        async def ask(id64, part, url, params=None, timeout=None):
            self.asked.append((id64, part, params, timeout))
            return self.answer
        self.answer = (ANSWER, None)
        self.state._canonn_ask = ask
        self.state.canonn_reports = True
        self.now = time.time()

    def at(self, s):
        return ed_outrider.iso_ts(self.now - 30 + s)

    def arrive(self, s=0, system=SYSTEM, name=NAME):
        self.j.handle({"event": "FSDJump", "timestamp": self.at(s), "StarSystem": name, "SystemAddress": system,
                       "StarPos": [0, 0, 0]})
        return dict(self.j.jump_arrival)

    def fss(self, s, kind="Ring", n=1, system=SYSTEM):
        for _ in range(n):
            self.j.handle({"event": "FSSSignalDiscovered", "timestamp": self.at(s), "SystemAddress": system,
                           "SignalName": f"$Fixed_Event_Life_{kind};", "SignalType": "Codex"})

    def said(self, kind=None):
        return [m for m in self.j.moments if m["kind"] in ((kind,) if kind else ("phenomena", "phenomena_reported"))]

    def report(self, a):
        asyncio.run(self.state.nsp_report(a))

    def test_reported_on_arrival_then_the_fss_is_quiet(self):
        a = self.arrive()
        self.report(a)
        self.assertEqual(self.asked, [(SYSTEM, "poi", {"system": NAME, "odyssey": "Y"}, ed_outrider.NSP_REPORT_TIMEOUT)])
        m = self.said("phenomena_reported")
        self.assertEqual([e["name"] for e in m[0]["entries"]], ["Albulum Gourd Mollusc", "Prasinum Metallic Crystals"])
        self.assertEqual((m[0]["system"], m[0]["system_name"]), (str(SYSTEM), NAME))
        self.fss(20, n=2)                                           # the FSS lists them a minute later: said already
        self.assertEqual(len(self.said()), 1)
        self.assertEqual(self.db.execute("SELECT n FROM phenomena WHERE system=?", (SYSTEM,)).fetchone()[0], 2)   # still kept
        # Now and Here name them from the cached answer (the panel never asks Canonn itself)
        self.state.canonn_cache[SYSTEM] = {"poi": (time.time(), ANSWER, None)}
        names = [e["name"] for e in self.state.system_detail(SYSTEM)["phenomena_reported"]]
        self.assertEqual(names, ["Albulum Gourd Mollusc", "Prasinum Metallic Crystals"])

    def test_what_you_logged_here_is_left_out(self):
        self.db.execute("INSERT INTO codex (ts, entry_id, name, system, region) VALUES (?, ?, ?, ?, ?)",
                        (self.at(-5000), CRYSTALS, "Prasinum Metallic Crystals", SYSTEM, "Inner Orion Spur"))
        a = self.arrive()
        self.report(a)
        self.assertEqual([e["name"] for e in self.said("phenomena_reported")[0]["entries"]], ["Albulum Gourd Mollusc"])
        self.state.canonn_cache[SYSTEM] = {"poi": (time.time(), ANSWER, None)}
        here = {e["name"]: e["here"] for e in self.state.system_detail(SYSTEM)["phenomena_reported"]}
        self.assertEqual(here, {"Albulum Gourd Mollusc": False, "Prasinum Metallic Crystals": True})   # Now marks it ✓

    def test_all_logged_here_says_nothing(self):
        for e in (MOLLUSC, CRYSTALS):
            self.db.execute("INSERT INTO codex (ts, entry_id, name, system) VALUES (?, ?, ?, ?)", (self.at(-5000), e, "x", SYSTEM))
        a = self.arrive()
        self.report(a)
        self.assertEqual(self.said(), [])
        self.fss(20)                                                # nothing told: the FSS says it as before
        self.assertEqual(len(self.said("phenomena")), 1)

    def test_new_to_your_codex_in_this_region(self):
        # the mollusc logged in another system of this region, the crystals in another region: only they are new here
        self.db.execute("INSERT INTO codex (ts, entry_id, name, system) VALUES (?, ?, ?, ?)", (self.at(-5000), MOLLUSC, "x", 11))
        self.db.execute("INSERT INTO codex (ts, entry_id, name, system) VALUES (?, ?, ?, ?)", (self.at(-4000), CRYSTALS, "x", 12))
        where = {SYSTEM: ("A", 18, 0, 0), 11: ("B", 18, 0, 0), 12: ("C", 7, 0, 0)}
        a = self.arrive()
        with mock.patch.object(self.state, "locate", lambda i: where.get(i)), \
                mock.patch.object(ed_outrider.outrider.bio, "region_number", lambda x, y, z: int(x)):
            self.report(a)
        self.assertEqual({e["name"]: e["new"] for e in self.said("phenomena_reported")[0]["entries"]},
                         {"Albulum Gourd Mollusc": False, "Prasinum Metallic Crystals": True})

    def test_gone_or_late_says_nothing(self):
        a = self.arrive()
        self.arrive(5, system=99, name="Elsewhere")                 # jumped on before Canonn answered
        self.report(a)
        self.assertEqual(self.said(), [])
        b = self.arrive(10)
        self.state.nsp_report_say(b, [MOLLUSC], now=self.now - 20 + ed_outrider.NSP_REPORT_WAIT_S + 1)
        self.assertEqual(self.said(), [])
        # a journal caught up on: the arrival is old news, nothing is asked
        asked = len(self.asked)
        self.state.nsp_report_key = None
        self.j.jump_arrival = dict(b, ts=ed_outrider.iso_ts(self.now - 3600))
        self.state.maybe_nsp_report()
        self.assertEqual(len(self.asked), asked)
        self.assertIsNone(self.state.nsp_report_task)

    def test_once_per_arrival(self):
        self.arrive()

        async def go():
            self.state.maybe_nsp_report()
            self.state.maybe_nsp_report()                           # the next tick: the same arrival
            await self.state.nsp_report_task
        asyncio.run(go())
        self.assertEqual(len(self.asked), 1)
        self.assertEqual(len(self.said("phenomena_reported")), 1)

    def test_canonn_down_falls_back_to_your_record(self):
        self.answer = (None, "Canonn could not be reached (ClientError)")
        self.db.execute("INSERT INTO phenomena (system, kind, ts, reached_ts, n) VALUES (?, 'ring', ?, NULL, 3)", (SYSTEM, self.at(-9000)))
        a = self.arrive()
        self.report(a)
        m = self.said()
        self.assertEqual([(x["kind"], x["count"], x["visited"], x.get("revisit")) for x in m], [("phenomena", 3, 0, True)])

    def test_off_your_own_record_only(self):
        """[server] canonn_reports off: Canonn is never asked; a system you know has sites left is said as you arrive."""
        self.state.canonn_reports = False
        self.db.execute("INSERT INTO phenomena (system, kind, ts, reached_ts, n) VALUES (?, 'ring', ?, ?, 3)",
                        (SYSTEM, self.at(-9000), self.at(-8000)))
        self.db.execute("INSERT INTO phenomena_sites VALUES (?, 'ring', ?, 'drop:1')", (SYSTEM, self.at(-8000)))
        self.arrive()
        self.state.maybe_nsp_report()                               # no event loop needed: nothing to ask
        self.assertEqual(self.asked, [])
        m = self.said()
        self.assertEqual([(x["kind"], x["count"], x["visited"], x["kinds"]) for x in m], [("phenomena", 3, 1, {"ring": 3})])
        self.fss(20, n=3)                                           # the FSS listing on this visit: told already
        self.assertEqual(len(self.said()), 1)

    def test_a_system_with_nothing_says_nothing(self):
        self.state.canonn_reports = False
        self.arrive()
        self.state.maybe_nsp_report()
        self.assertEqual(self.said(), [])


class FssRule(unittest.TestCase):
    """The FSS listing is news while the system has sites you have not dropped at, once a visit (was: only in a
    system with none on record, so a revisit with sites left said nothing)."""
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.now = time.time()

    def at(self, s):
        return ed_outrider.iso_ts(self.now - 3000 + s)

    def visit(self, s):
        self.j.handle({"event": "FSDJump", "timestamp": self.at(s), "StarSystem": "Sys R", "SystemAddress": 7, "StarPos": [0, 0, 0]})

    def listing(self, s):
        for _ in range(3):
            self.j.handle({"event": "FSSSignalDiscovered", "timestamp": self.at(s), "SystemAddress": 7,
                           "SignalName": "$Fixed_Event_Life_Ring;", "SignalType": "Codex"})

    def drop(self, s):
        self.j.handle({"event": "SupercruiseDestinationDrop", "timestamp": self.at(s), "Type": "$Fixed_Event_Life_Ring;"})

    def said(self):
        return [(m["count"], m["visited"]) for m in self.j.moments if m["kind"] == "phenomena"]

    def test_revisits(self):
        self.visit(2900)                                            # these moments are live: the last minutes
        self.listing(2905)
        self.drop(2910)
        self.listing(2950)                                          # the FSS again, same visit: said already
        self.assertEqual(self.said(), [(3, 0)])
        self.visit(2960)                                            # back again, one of three visited
        self.listing(2965)
        self.assertEqual(self.said(), [(3, 0), (3, 1)])
        self.drop(2970)
        self.drop(2975)                                             # all three dropped at
        self.visit(2985)
        self.listing(2990)
        self.assertEqual(self.said(), [(3, 0), (3, 1)])             # nothing left: quiet


class Setting(unittest.TestCase):
    def test_canonn_reports(self):
        args = argparse.Namespace(journals=None, legacy=None, host=None, port=None, radius=None, db=None)
        self.assertTrue(ed_outrider.settings_from({}, args, None, ([], []))["canonn_reports"])
        st = ed_outrider.settings_from({"server": {"canonn_reports": False}}, args, None, ([], []))
        self.assertFalse(st["canonn_reports"])
        self.assertIn("canonn_reports = false   # ", ed_outrider.config_text(st))
        self.assertIn(("server", "canonn_reports"), [k for _, _, keys in CE.GROUPS for k in keys])


if __name__ == "__main__":
    unittest.main()
