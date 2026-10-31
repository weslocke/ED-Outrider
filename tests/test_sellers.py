"""The nearest places to sell (State.maybe_find_sellers, sellers_summary): Now's at-risk line names one you can fly to.
Fakes only, no Spansh."""
import asyncio
import types
import unittest

from support import ed_outrider  # also puts the repository root on sys.path
import outrider.cargo as cargo  # noqa: E402


def place(name, d, carrier):
    return {"name": name, "system": f"Sys {name}", "id64": str(1000 + d), "distance": d,
            "type": cargo.CARRIER_TYPE if carrier else "Coriolis Starport", "updated_at": "2026-10-29T00:00:00Z",
            "ls": 100, "large_pad": True, "x": float(d), "y": 0.0, "z": 0.0}


class Sellers(unittest.TestCase):
    def setUp(self):
        self.db = ed_outrider.open_db(":memory:")
        self.addCleanup(self.db.close)
        self.j = ed_outrider.Journals(self.db)
        self.state = ed_outrider.State(self.db, self.j, types.SimpleNamespace(cached=lambda i: (None, None)), 25)
        self.j.pos = {"id64": 1, "name": "Deep", "x": 0.0, "y": 0.0, "z": 0.0}
        self.asked = []

        async def stations(service, pos, size=20, permanent=False):
            self.asked.append((service, permanent))
            if permanent:
                return [place("Far Port", 900, False)]
            return [place(f"C{i}", 10 + i, True) for i in range(20)]   # the 20 nearest: other players' carriers
        self.state.spansh = types.SimpleNamespace(stations=stations)

    def test_all_carriers_nearest(self):
        """Review 8: when the 20 nearest UC / Vista places are all other players' carriers, the nearest permanent
        stations are asked for too, so Now's sell line names a place (it named none, far out where it matters most)."""
        async def go():
            self.state.maybe_find_sellers()
            await self.state.seller_task
        asyncio.run(go())
        self.assertEqual(self.asked, [("Universal Cartographics", False), ("Vista Genomics", False),
                                      ("Universal Cartographics", True), ("Vista Genomics", True)])
        s = self.state.sellers_summary()
        self.assertEqual((s["uc"]["sell"]["name"], s["vista"]["sell"]["name"], s["uc"]["nearest"]["name"]),
                         ("Far Port", "Far Port", "C0"))


if __name__ == "__main__":
    unittest.main()
