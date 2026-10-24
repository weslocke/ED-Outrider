"""Four mining additions, ideas from EliteMining's feature list (project/PLAN-mining-ideas-2026-10-24.md): Search's
"2+ in a ring" (C) and a mining mission's search (D) here; the per-mineral thresholds (A) and the ring's prices (B)
are the page's, in tests/page_smoke.js. Fakes only."""
import asyncio
import time
import unittest

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.commander as commander  # noqa: E402

CRIT = {"stars": set(), "planets": set(), "rings": set(), "hotspots": {"Painite"}}


class HotspotsMin(unittest.TestCase):
    """C: a ring with two or more hotspots of one ticked mineral, Local and Spansh."""

    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        now = time.time()
        self.j.handle({"event": "FSDJump", "timestamp": ed_outrider.iso_ts(now - 30), "StarSystem": "Home", "SystemAddress": 9,
                       "StarPos": [0, 0, 0]})
        rings = lambda n: [{"name": "A Ring", "type": "Metallic", "hotspots": {"Painite": n, "Platinum": 3}}]
        for i, (name, n) in enumerate((("One Painite", 1), ("Two Painite", 2))):
            base = {"name": name, "x": 10.0 + i, "y": 0.0, "z": 0.0,
                    "records": [{"name": f"{name} 1", "type": "Planet", "subtype": "Icy body", "full": True, "rings": rings(n)}]}
            self.db.execute("INSERT INTO spansh_systems (id64, updated_at, summary, fetched_ts, x, y, z) VALUES (?, 'x', ?, ?, ?, 0, 0)",
                            (100 + i, ed_outrider.json.dumps(base), now, 10.0 + i))
        self.db.commit()

    def search(self, params, spansh=None):
        s = ed_outrider.Searcher(ed_outrider.State(self.db, self.j, spansh or ed_outrider.Spansh(self.db), 25))

        async def go():
            s.start(dict({"radius": 50}, **params))
            await s.task
        asyncio.run(go())
        return s.result

    def test_match_system(self):
        recs = [{"name": "S 1", "type": "Planet", "rings": [{"name": "A Ring", "type": "Metallic", "hotspots": {"Painite": 1}},
                                                            {"name": "B Ring", "type": "Metallic", "hotspots": {"Painite": 2}}]}]
        one = ed_outrider.match_system("S", recs, CRIT)["hotspots"]
        two = ed_outrider.match_system("S", recs, dict(CRIT, hotspots_min=2))["hotspots"]
        self.assertEqual([h["t"] for h in one], ["S 1 A Ring (Metallic): Painite 1", "S 1 B Ring (Metallic): Painite 2"])
        self.assertEqual([h["t"] for h in two], ["S 1 B Ring (Metallic): Painite 2"])
        lone = [dict(recs[0], rings=recs[0]["rings"][:1])]   # one Painite hotspot only: no match at 2+
        self.assertNotIn("hotspots", ed_outrider.match_system("S", lone, dict(CRIT, hotspots_min=2)))

    def test_local(self):
        names = lambda r: [x["name"] for x in r["results"]]
        self.assertEqual(sorted(names(self.search({"source": "local", "hotspots": ["Painite"]}))), ["One Painite", "Two Painite"])
        self.assertEqual(names(self.search({"source": "local", "hotspots": ["Painite"], "hotspots_min": 2})), ["Two Painite"])
        # only 2 means 2+: anything else is the plain search
        self.assertEqual(len(self.search({"source": "local", "hotspots": ["Painite"], "hotspots_min": 7})["results"]), 2)

    def test_spansh_filter(self):
        asked = []

        class Fake:
            async def body_search(self, filters, pos, radius, pages):
                asked.append(filters)
                return [], None
        self.search({"source": "spansh", "hotspots": ["Painite"], "hotspots_min": 2}, Fake())
        self.search({"source": "spansh", "hotspots": ["Painite"]}, Fake())
        self.assertEqual([f["ring_signals"][0]["value"] for f in asked], [[2, 9999], [1, 9999]])


class RingPriceNames(unittest.TestCase):
    """B: the page asks the Sell lookup by the hotspot's own name; every one of them is a commodity Spansh prices
    (so the lookup finds it by its letters: "Void Opal" is the journal's "opal")."""

    def test_every_hotspot_mineral_is_priced(self):
        from test_cargo import spansh_commodity_names
        import outrider.cargo as cargo
        names = {cargo.norm(n) for n in spansh_commodity_names()}
        self.assertEqual([m for m in ed_outrider.HOTSPOT_MINERALS if cargo.norm(m) not in names], [])


class MiningMission(unittest.TestCase):
    """D: a mining mission is marked, with its commodity's journal id (the search follows the id, not the words)."""

    def accepted(self, name, commodity="$Bertrandite_Name;", local="Bertrandite"):
        e = {"event": "MissionAccepted", "timestamp": "2026-10-24T10:00:00Z", "MissionID": 1, "Name": name, "Faction": "F",
             "Expiry": "2026-10-30T10:00:00Z", "Reward": 100}
        if commodity:
            e.update(Commodity=commodity, Commodity_Localised=local, Count=20)
        return commodity_row(e)

    def test_marked(self):
        m = self.accepted("Mission_Mining_name", local="Bertrandit")   # a German game: the id still says what it is
        self.assertEqual((m["mining"], m["commodity_id"], m["commodity"]), (True, "bertrandite", "Bertrandit"))
        self.assertEqual(self.accepted("Mission_MiningWing_name", "$LowTemperatureDiamond_Name;")["commodity_id"], "lowtemperaturediamond")
        c = self.accepted("Mission_Delivery_name", "$Gold_Name;", "Gold")
        self.assertEqual((c["mining"], c["commodity_id"]), (False, "gold"))
        self.assertEqual(self.accepted("Mission_Mining_name", None)["commodity_id"], None)


def commodity_row(e):
    state = commander.apply("missions", None, e, {})
    [row] = commander.missions(state, now=ed_outrider.ts_seconds("2026-10-24T11:00:00Z"))
    return row


if __name__ == "__main__":
    unittest.main()
