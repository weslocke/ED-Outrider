"""Shared fixtures, fakes and helpers for the unit tests (tests/test_*.py).

Importing this module puts the repository root on sys.path, so the tests can import ed_outrider and outrider.
Helpers that one test class shares with others live here (the owner class keeps its attribute as an alias).
"""
import argparse
import datetime as dt
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ed_outrider  # noqa: E402

# Never the player's own journal folders: the server auto-detects them at import, and anything that writes into a live
# folder (the uploads' lease files) would write into the real one. A test that needs folders sets its own.
ed_outrider.LIVE_DIRS[:] = []
# whether this machine runs Outrider as the systemd service changes the restore command's words: never in a test
# (a test that wants it says so)
ed_outrider.systemd_service_installed = lambda: False
# ...nor this desktop's keyboard layout (the Auto-target box's typing word): a test that wants one passes its own
import outrider.target  # noqa: E402
REAL_KEYBOARD_LAYOUT = outrider.target.keyboard_layout   # the function itself, for its own test (with fakes)
outrider.target.keyboard_layout = lambda run=None, platform=None: None
ed_outrider.LEGACY_DIRS[:] = []
# ...nor the player's config file: the Uploads switch writes [eddn]/[edsm] enabled into it
import tempfile  # noqa: E402
ed_outrider.CONFIG_PATH = os.path.join(tempfile.mkdtemp(prefix="outrider-test-config-"), "ed_outrider.toml")
# ...nor EDMC's config on this PC (the uploads' check reads it): a test that wants it passes its own home folder
import outrider.uploads  # noqa: E402
_edmc_uploads = outrider.uploads.edmc_uploads
outrider.uploads.edmc_uploads = lambda home=None, **kw: _edmc_uploads(home=home, **kw) if home else None
# ...nor the player's fetched picture list (data/codex_images.json): the shipped one, or a test's own
import outrider.codex_images  # noqa: E402
outrider.codex_images.CACHE = os.path.join(tempfile.mkdtemp(prefix="outrider-test-images-"), "codex_images.json")
# ...nor the player's ~/.config/systemd/user or Startup folder (S70's service), nor systemctl itself: a scratch folder,
# and a runner that refuses (a test that wants systemctl's answers sets its own fake)
import outrider.service  # noqa: E402
outrider.service.TARGET_DIR = tempfile.mkdtemp(prefix="outrider-test-service-")


def _no_systemctl(cmd, **kw):
    raise OSError(f"tests never run {cmd[0]}")


outrider.service.RUNNER = _no_systemctl


def user_docs():
    """The user documentation as one text: README.md and every page of docs/guide/ (the README is a front page since
    2026-10-07; tests that check what the docs say read all of it)."""
    import glob
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parts = []
    for path in [os.path.join(root, "README.md")] + sorted(glob.glob(os.path.join(root, "docs", "guide", "*.md"))):
        with open(path, encoding="utf-8") as f:
            parts.append(f.read())
    return "\n".join(parts)


def T(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


ARGS = argparse.Namespace(commander=None, since=None, ignore_deaths=False, bonus_rate=None,
                          efficiency_bonus=False, no_odyssey=False, top=0)


def scan(ts, system, addr, body_id, name, disc=False, star=False):
    ev = {"event": "Scan", "timestamp": ts, "StarSystem": system, "SystemAddress": addr, "BodyID": body_id,
          "BodyName": name, "WasDiscovered": disc, "WasMapped": False, "ScanType": "Detailed",
          "DistanceFromArrivalLS": 0.0 if star else 500.0}
    if star:
        ev.update(StarType="K", StellarMass=0.8)
    else:
        ev.update(PlanetClass="High metal content body", MassEM=1.0, TerraformState="")
    return (T(ts), None, ev)


def sale(ts, systems):
    return (T(ts), None, {"event": "MultiSellExplorationData", "timestamp": ts, "TotalEarnings": 1000, "BaseValue": 1000,
                          "Bonus": 0, "Discovered": [{"SystemName": s, "NumBodies": 1} for s in systems]})


def death(ts, option="rebuy"):
    return [(T(ts), None, {"event": "Died", "timestamp": ts}), (T(ts), None, {"event": "Resurrect", "timestamp": ts, "Option": option})]


def org(ts, system, body, species, kind):
    return {"event": "ScanOrganic", "timestamp": ts, "SystemAddress": system, "Body": body, "ScanType": kind,
            "Species": f"$Codex_Ent_{species};", "Species_Localised": "Bacterium Aurasus",
            "Genus_Localised": "Bacterium", "Variant_Localised": "Bacterium Aurasus - Teal"}


def B(name, bid=None, parents=None, kind="Planet", main=False):
    pf = None if parents is None else [{"kind": k, "id": v} for k, v in parents]
    return {"name": name, "body_id": bid, "parents_full": pf, "type": kind, "main": main}


def shape(nodes):
    """A tree as nested tuples of names/labels, for readable assertions."""
    return [(n.get("name") or n["label"], shape(n["children"])) if n["children"] else (n.get("name") or n["label"]) for n in nodes]


class _FakeResponse:
    """A urlopen() result for the download tests: serves `data` in chunks, then fails with `fail` if set."""

    def __init__(self, data, fail=None, length=None):
        self.data, self.fail = data, fail
        self.headers = {"Content-Length": str(len(data) if length is None else length)}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n):
        if not self.data:
            if self.fail:
                raise self.fail
            return b""
        chunk, self.data = self.data[:n], self.data[n:]
        return chunk


def types_ns(**kw):
    import types
    return types.SimpleNamespace(**kw)


Q = ed_outrider.SALE_QUIET_S   # s: the wait for a sale's next page


RHINO_SESSION = [
    'J {"timestamp":"2026-09-30T02:53:30Z", "event":"Location", "Docked":true, "StationName":"G0X-85Z", "StationType":"FleetCarrier", "StarSystem":"Smojooe AR-E b25-8", "SystemAddress":18207037532889, "StarPos":[-4177.09375, -1.0, 3324.53125]}',
    'J { "timestamp":"2026-09-30T03:06:20Z", "event":"SupercruiseExit", "Taxi":false, "Multicrew":false, "StarSystem":"Smojooe AR-E b25-8", "SystemAddress":18207037532889, "Body":"Smojooe AR-E b25-8 ABC 3 d", "BodyID":19, "BodyType":"Planet" }',
    'J { "timestamp":"2026-09-30T03:07:25Z", "event":"LaunchSRV", "SRVType":"mev_rhino", "SRVType_Localised":"SRV Rhino", "Loadout":"base", "ID":51, "PlayerControlled":true }',
    'S {"timestamp":"2026-09-30T03:10:13Z", "event":"Status", "Flags":203456584, "Flags2":0, "GuiFocus":0, "Cargo":0.0, "Latitude":-53.79417, "Longitude":-144.581131, "Heading":177, "Altitude":1, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:16:46Z", "event":"Status", "Flags":203456584, "Flags2":0, "GuiFocus":4, "Cargo":0.0, "Latitude":-53.794037, "Longitude":-144.581116, "Heading":176, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:16:48Z", "event":"Status", "Flags":203456584, "Flags2":0, "GuiFocus":3, "Cargo":0.0, "Latitude":-53.794037, "Longitude":-144.581116, "Heading":176, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:16:49Z", "event":"Status", "Flags":203456584, "Flags2":0, "GuiFocus":1, "Cargo":0.0, "Latitude":-53.794037, "Longitude":-144.581116, "Heading":176, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:16:56Z", "event":"MiningRefined", "Type":"$water_name;", "Type_Localised":"Water" }',
    'J { "timestamp":"2026-09-30T03:16:56Z", "event":"MaterialCollected", "Category":"Raw", "Name":"nickel", "Count":1 }',
    'S {"timestamp":"2026-09-30T03:16:57Z", "event":"Status", "Flags":203456584, "Flags2":0, "GuiFocus":1, "Cargo":2.0, "Latitude":-53.794037, "Longitude":-144.581116, "Heading":176, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:16:57Z", "event":"MiningRefined", "Type":"$water_name;", "Type_Localised":"Water" }',
    'J { "timestamp":"2026-09-30T03:16:58Z", "event":"MiningRefined", "Type":"$water_name;", "Type_Localised":"Water" }',
    'S {"timestamp":"2026-09-30T03:16:59Z", "event":"Status", "Flags":203456584, "Flags2":0, "GuiFocus":1, "Cargo":4.0, "Latitude":-53.794037, "Longitude":-144.581116, "Heading":176, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:16:59Z", "event":"MiningRefined", "Type":"$water_name;", "Type_Localised":"Water" }',
    'S {"timestamp":"2026-09-30T03:17:00Z", "event":"Status", "Flags":203456584, "Flags2":0, "GuiFocus":0, "Cargo":4.0, "Latitude":-53.794037, "Longitude":-144.581116, "Heading":176, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:17:00Z", "event":"MiningRefined", "Type":"$water_name;", "Type_Localised":"Water" }',
    'S {"timestamp":"2026-09-30T03:17:01Z", "event":"Status", "Flags":203456584, "Flags2":0, "GuiFocus":0, "Cargo":5.0, "Latitude":-53.794037, "Longitude":-144.581116, "Heading":176, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:17:02Z", "event":"MiningRefined", "Type":"$water_name;", "Type_Localised":"Water" }',
    'S {"timestamp":"2026-09-30T03:17:02Z", "event":"Status", "Flags":203456584, "Flags2":0, "GuiFocus":0, "Cargo":6.0, "Latitude":-53.794037, "Longitude":-144.581116, "Heading":176, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:17:03Z", "event":"MiningRefined", "Type":"$water_name;", "Type_Localised":"Water" }',
    'S {"timestamp":"2026-09-30T03:17:03Z", "event":"Status", "Flags":203456584, "Flags2":0, "GuiFocus":0, "Cargo":7.0, "Latitude":-53.794037, "Longitude":-144.581116, "Heading":176, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:17:04Z", "event":"Status", "Flags":203456584, "Flags2":0, "GuiFocus":0, "Cargo":8.0, "Latitude":-53.794037, "Longitude":-144.581116, "Heading":176, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:17:04Z", "event":"MiningRefined", "Type":"$water_name;", "Type_Localised":"Water" }',
    'J { "timestamp":"2026-09-30T03:17:05Z", "event":"MiningRefined", "Type":"$water_name;", "Type_Localised":"Water" }',
    'S {"timestamp":"2026-09-30T03:17:06Z", "event":"Status", "Flags":203456584, "Flags2":0, "GuiFocus":0, "Cargo":9.0, "Latitude":-53.794037, "Longitude":-144.581116, "Heading":176, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:17:07Z", "event":"MiningRefined", "Type":"$water_name;", "Type_Localised":"Water" }',
    'S {"timestamp":"2026-09-30T03:17:07Z", "event":"Status", "Flags":203456584, "Flags2":0, "GuiFocus":0, "Cargo":10.0, "Latitude":-53.794037, "Longitude":-144.581116, "Heading":176, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:22:59Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":10.0, "Latitude":-53.869118, "Longitude":-144.48291, "Heading":158, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:29:46Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":10.0, "Latitude":-53.868958, "Longitude":-144.482742, "Heading":302, "Altitude":1, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:29:50Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:29:51Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":11.0, "Latitude":-53.868797, "Longitude":-144.483139, "Heading":303, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:29:51Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:29:52Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":12.0, "Latitude":-53.868797, "Longitude":-144.483139, "Heading":303, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:29:53Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:29:53Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":13.0, "Latitude":-53.868797, "Longitude":-144.483139, "Heading":303, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:29:54Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:29:55Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":14.0, "Latitude":-53.868797, "Longitude":-144.483139, "Heading":303, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:29:55Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:29:56Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":15.0, "Latitude":-53.868797, "Longitude":-144.483139, "Heading":303, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:29:57Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:29:57Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":16.0, "Latitude":-53.868797, "Longitude":-144.483139, "Heading":303, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:29:58Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:29:59Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":17.0, "Latitude":-53.868797, "Longitude":-144.483139, "Heading":303, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:29:59Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:30:00Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":18.0, "Latitude":-53.868797, "Longitude":-144.483139, "Heading":303, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:30:01Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:30:02Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":19.0, "Latitude":-53.868797, "Longitude":-144.483139, "Heading":303, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:30:03Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:30:03Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":20.0, "Latitude":-53.868797, "Longitude":-144.483139, "Heading":303, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:30:04Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:30:05Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":21.0, "Latitude":-53.868797, "Longitude":-144.483139, "Heading":303, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:33:17Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":21.0, "Latitude":-53.868618, "Longitude":-144.483551, "Heading":310, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:33:18Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:33:19Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":22.0, "Latitude":-53.868687, "Longitude":-144.483444, "Heading":309, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:33:20Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:33:20Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":23.0, "Latitude":-53.868687, "Longitude":-144.483444, "Heading":309, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:33:21Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":24.0, "Latitude":-53.868687, "Longitude":-144.483444, "Heading":309, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:33:21Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:33:23Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":2, "Cargo":24.0, "Latitude":-53.868687, "Longitude":-144.483444, "Heading":309, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:33:28Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":24.0, "Latitude":-53.868687, "Longitude":-144.483444, "Heading":309, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:35:21Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":24.0, "Latitude":-53.869404, "Longitude":-144.481781, "Heading":323, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:38:29Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":24.0, "Latitude":-53.869209, "Longitude":-144.482346, "Heading":310, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:38:30Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":24.0, "Latitude":-53.8689, "Longitude":-144.48291, "Heading":308, "Altitude":1, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:38:31Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":25.0, "Latitude":-53.86887, "Longitude":-144.482971, "Heading":308, "Altitude":1, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:38:31Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'J { "timestamp":"2026-09-30T03:38:32Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:38:33Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":26.0, "Latitude":-53.86887, "Longitude":-144.482971, "Heading":308, "Altitude":1, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:38:34Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:38:34Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":27.0, "Latitude":-53.86887, "Longitude":-144.482971, "Heading":308, "Altitude":1, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:38:35Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":28.0, "Latitude":-53.86887, "Longitude":-144.482971, "Heading":308, "Altitude":1, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:38:35Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'J { "timestamp":"2026-09-30T03:38:36Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:38:37Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":29.0, "Latitude":-53.86887, "Longitude":-144.482971, "Heading":308, "Altitude":1, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:38:37Z", "event":"MiningRefined", "Type":"$methanolmonohydratecrystals_name;", "Type_Localised":"Methanol Monohydrate Crystals" }',
    'S {"timestamp":"2026-09-30T03:38:38Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":30.0, "Latitude":-53.86887, "Longitude":-144.482971, "Heading":308, "Altitude":1, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:38:41Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":2, "Cargo":30.0, "Latitude":-53.86887, "Longitude":-144.482971, "Heading":308, "Altitude":1, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:38:45Z", "event":"Status", "Flags":471892040, "Flags2":0, "GuiFocus":0, "Cargo":30.0, "Latitude":-53.86887, "Longitude":-144.482971, "Heading":308, "Altitude":1, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:41:17Z", "event":"Status", "Flags":471908424, "Flags2":0, "GuiFocus":0, "Cargo":30.0, "Latitude":-53.864246, "Longitude":-144.48613, "Heading":346, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'J { "timestamp":"2026-09-30T03:41:31Z", "event":"DockSRV", "SRVType":"mev_rhino", "SRVType_Localised":"SRV Rhino", "ID":51 }',
    'S {"timestamp":"2026-09-30T03:41:31Z", "event":"Status", "Flags":471875656, "Flags2":0, "GuiFocus":0, "Cargo":30.0, "Latitude":-53.864037, "Longitude":-144.486206, "Heading":341, "Altitude":0, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
    'S {"timestamp":"2026-09-30T03:41:33Z", "event":"Status", "Flags":153092104, "Flags2":0, "GuiFocus":0, "Cargo":30.0, "Latitude":-53.861923, "Longitude":-144.487473, "Heading":341, "Altitude":30, "BodyName":"Smojooe AR-E b25-8 ABC 3 d", "PlanetRadius":1204549.875}',
]


class _HwResp:
    """A Spansh answer for the Highway tests: an HTTP status and a JSON body (or an exception json() raises)."""

    def __init__(self, status, body):
        self.status, self.body = status, body

    async def json(self, content_type=None):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body

    def raise_for_status(self):
        if self.status >= 400:
            raise ed_outrider.ClientError(f"HTTP {self.status}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _HwSession:
    """A stand-in aiohttp session: each get() takes the next scripted answer (the last one repeats); an exception in
    the script is raised by get() itself (Spansh unreachable). Nothing here touches the network."""

    def __init__(self, script):
        self.script, self.calls = list(script), []

    def get(self, url, params=None, **kw):   # kw: a timeout and the like, as aiohttp's get takes them
        self.calls.append((url, dict(params or {})))
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return _HwResp(*item)

    def post(self, url, data=None, json=None):
        """A job submitted with form fields (Road to Riches), or a JSON search: recorded as ("POST", url, fields or
        the JSON body), answered like get(). A repeated form field (data as a list of pairs) is recorded as a list."""
        fields = {}
        for k, v in (data.items() if isinstance(data, dict) else data or []):
            fields[k] = (fields[k] if isinstance(fields[k], list) else [fields[k]]) + [v] if k in fields else v
        self.calls.append(("POST", url, json if json is not None else fields))
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return _HwResp(*item)


# The author's keyboard bindings for auto-target, copied (read only) from the active preset "HCS X56 Attempt 1"
# (StartPreset.4.start, HCS X56 Attempt 1.4.2.binds): the joystick bindings first, the keyboard ones second, as there
AUTHOR_BINDS = """<?xml version="1.0" encoding="UTF-8" ?>
<Root PresetName="HCS X56 Attempt 1" MajorVersion="4" MinorVersion="2">
	<PrimaryFire>
		<Primary Device="SaitekX56Joystick" Key="Joy_1" />
		<Secondary Device="Keyboard" Key="Key_K">
			<Modifier Device="Keyboard" Key="Key_LeftAlt" />
			<Modifier Device="Keyboard" Key="Key_RightAlt" />
		</Secondary>
	</PrimaryFire>
	<GalaxyMapOpen>
		<Primary Device="SaitekX56Throttle" Key="Joy_18" />
		<Secondary Device="Keyboard" Key="Key_T">
			<Modifier Device="Keyboard" Key="Key_LeftAlt" />
			<Modifier Device="Keyboard" Key="Key_RightAlt" />
		</Secondary>
	</GalaxyMapOpen>
	<UI_Up>
		<Primary Device="SaitekX56Throttle" Key="Joy_24" />
		<Secondary Device="Keyboard" Key="Key_W" />
	</UI_Up>
	<UI_Down>
		<Primary Device="SaitekX56Throttle" Key="Joy_26" />
		<Secondary Device="Keyboard" Key="Key_S" />
	</UI_Down>
	<UI_Left>
		<Primary Device="SaitekX56Throttle" Key="Joy_27" />
		<Secondary Device="Keyboard" Key="Key_A" />
	</UI_Left>
	<UI_Right>
		<Primary Device="SaitekX56Throttle" Key="Joy_25" />
		<Secondary Device="Keyboard" Key="Key_D" />
	</UI_Right>
	<UI_Select>
		<Primary Device="SaitekX56Joystick" Key="Joy_1" />
		<Secondary Device="Keyboard" Key="Key_Space" />
	</UI_Select>
	<UI_Back>
		<Primary Device="SaitekX56Joystick" Key="Joy_2" />
		<Secondary Device="Keyboard" Key="Key_Backspace" />
	</UI_Back>
	<CycleNextPanel>
		<Primary Device="SaitekX56Throttle" Key="Joy_21" />
		<Secondary Device="Keyboard" Key="Key_W">
			<Modifier Device="Keyboard" Key="Key_LeftAlt" />
			<Modifier Device="Keyboard" Key="Key_RightAlt" />
		</Secondary>
	</CycleNextPanel>
	<CamYawRight>
		<Primary Device="{NoDevice}" Key="" />
		<Secondary Device="Keyboard" Key="Key_X">
			<Modifier Device="Keyboard" Key="Key_LeftAlt" />
			<Modifier Device="Keyboard" Key="Key_RightShift" />
		</Secondary>
	</CamYawRight>
	<CamZoomOut>
		<Primary Device="{NoDevice}" Key="" />
		<Secondary Device="Keyboard" Key="Key_2">
			<Modifier Device="Keyboard" Key="Key_RightAlt" />
			<Modifier Device="Keyboard" Key="Key_Apps" />
		</Secondary>
	</CamZoomOut>
</Root>
"""


def _fake_evdev():
    """A stand-in evdev with key codes only: no UInput, so nothing here can ever create a real virtual keyboard."""
    import types
    import outrider.target
    names = {"KEY_" + c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"} | {k for k, _ in outrider.target.US_KEYMAP.values()}
    names |= {"KEY_LEFTALT", "KEY_RIGHTALT", "KEY_LEFTCTRL", "KEY_RIGHTCTRL", "KEY_LEFTSHIFT", "KEY_RIGHTSHIFT",
              "KEY_ENTER", "KEY_KPENTER", "KEY_BACKSPACE", "KEY_SPACE", "KEY_HOME", "KEY_ESC", "KEY_COMPOSE", "KEY_DOWN"}
    codes = {n: i + 1 for i, n in enumerate(sorted(names))}
    return types.SimpleNamespace(ecodes=types.SimpleNamespace(EV_KEY=1, ecodes=codes))


class FakeGame:
    """Stands in for the virtual keyboard's device (honker.ui) AND the game behind it: it records every key event
    and reacts like the galaxy map as far as the auto-target steps need (Alt+Alt+T toggles the map, which opens on
    its map; W highlights "Search the Galaxy" and Space then puts the cursor in it, while Space alone opens the
    current system and A/D move along the tab column; once in the box, typed keys and Ctrl+V fill it (a key bound to a
    control is a letter there too), its results list SUGGEST_S after the last change; Enter then selects the one
    result, but with several (every system whose name starts with the text: "Sol", "Solati") only leaves the box
    (found in game 2026-10-23); the down arrow highlights the first result (the whole name's system first) and Space
    then picks it (an Enter or arrow before then does nothing), Space held 0.5 s plots the route; or, the map's
    focus back after a found system, D (UI_Right) twice reaches the system panel's icon column (once: its details),
    S (UI_Down) goes down it, and Space on the ninth icon, Target System, makes the found system the target
    (discussion #12, the author's checks in game)
    to the system found), writing Status.json's fields into `status`. Nothing reaches a real device."""
    REVERSE = None
    TARGET_ICON = 8   # Target System: eight UI_Downs from the top of the icon column
    SUGGEST_S = 0.15   # s after the name changes before the search lists its suggestion (Enter selects nothing sooner)

    def __init__(self, evdev, status, systems=None):
        import outrider.target
        self.names = {v: k for k, v in evdev.ecodes.ecodes.items()}
        if FakeGame.REVERSE is None:
            FakeGame.REVERSE = {v: c for c, v in outrider.target.US_KEYMAP.items()}
        self.status = status
        self.systems = systems or {}
        self.down, self.writes, self.closed = set(), [], False
        self.tab, self.focused, self.text, self.found, self.select_at = 0, False, "", None, None
        self.search_lit, self.map_focus, self.lit = False, False, None
        self.panel, self.icon = 0, 0   # the system panel: 0 the map, 1 its details, 2 its icon column (icon: from the top)
        self.clipboard, self.text_at = None, 0.0
        # misbehaviours for the abort paths
        self.ignore_open = self.ignore_close = self.no_plot = False
        self.on_type = None   # called after each typed character (a panel opening mid-way, a jump...)
        self.on_close = None  # called when the map closes (a target showing up late, say)
        self.clock = time.time   # a FakeClock in the tests that run on fake time
        self.plot_to = None   # plot this id64 instead of the one found
        self.target_closes = False   # Target System closes the map by itself
        # the galaxy map's GuiFocus can lag in Status.json, or not come at all, where the journal's Music says it at once
        # (the author's recording, 2026-10-23): with status_lag the screen changes (`screen`) and Status.json does not;
        # `music` is the journal's Music tracks, one per opening and closing, as (track, when written): a closing's comes
        # music_delay s late, as the game's trailed Target System by 1-3 s; `fsd` the FSDTarget ids, written at once
        # (`music_now`, `fsd_now`: the run's view of them, what is written by now)
        self.status_lag, self.screen, self.music, self.music_delay, self.fsd = False, None, [], 0.0, []

    def screen_focus(self):
        return self.screen if self.status_lag else self.status.get("gui_focus")

    def set_focus(self, v):
        self.screen = v
        if not self.status_lag:
            self.status["gui_focus"] = v
        self.music.append(("GalaxyMap", self.clock()) if v == 6 else ("Supercruise", self.clock() + self.music_delay))

    def music_now(self):
        now = self.clock()
        seen = [m for m in self.music if (m[1] if isinstance(m, tuple) else 0) <= now]
        if not seen:
            return None
        last = seen[-1]
        return ("Journal.fake.log", len(seen), last[0] if isinstance(last, tuple) else last)

    def fsd_now(self):
        return ("Journal.fake.log", len(self.fsd), self.fsd[-1]) if self.fsd else None

    def write(self, _type, code, value):
        if self.closed:
            raise AttributeError("closed")
        name = self.names[code]
        self.writes.append((name, value))
        if value:
            self.down.add(name)
            self.key(name)
        else:
            self.down.discard(name)
            if name == "KEY_SPACE" and self.select_at is not None:
                held, self.select_at = self.clock() - self.select_at, None
                if held >= 0.5 and self.found is not None and self.map_focus and not self.no_plot:
                    self.status["destination"] = {"System": self.plot_to or self.found[1], "Body": 0, "Name": self.found[0]}

    def key(self, name):
        alts = {"KEY_LEFTALT", "KEY_RIGHTALT"} <= self.down
        if name == "KEY_T" and alts:
            if self.screen_focus() == 6 and not self.ignore_close:
                self.set_focus(0)
                if self.on_close:
                    self.on_close(self)
            elif not self.screen_focus() and not self.ignore_open:
                self.set_focus(6)
                self.tab, self.focused, self.text, self.found = 0, False, "", None
                self.search_lit, self.lit, self.panel, self.icon = False, None, 0, 0
            return
        if self.screen_focus() != 6 or name.endswith(("ALT", "SHIFT", "CTRL")) or name == "KEY_COMPOSE":   # modifiers
            return
        if self.lit is not None:   # a result highlighted: Space picks it (the map flies there; the focus stays in the panel)
            if name == "KEY_SPACE":
                self.found, self.lit, self.map_focus = (self.lit, self.systems[self.lit]), None, False
            return
        if self.focused:
            results = sorted((s for s in self.systems if s.lower().startswith(self.text.lower())), key=lambda s: (s != self.text, s))
            if name == "KEY_ENTER":   # selects the one result, once listed; the focus stays in the search panel
                if self.clock() - self.text_at < self.SUGGEST_S:
                    return
                self.focused, self.map_focus = False, False
                self.found = (self.text, self.systems.get(self.text)) if self.text in self.systems and len(results) == 1 else None
            elif name == "KEY_DOWN":   # into the results list, its first one highlighted
                if self.clock() - self.text_at >= self.SUGGEST_S and results:
                    self.focused, self.lit = False, results[0]
            elif name == "KEY_V" and {"KEY_LEFTCTRL"} <= self.down:
                self.text, self.text_at = self.text + (self.clipboard or ""), self.clock()
            else:
                self.text, self.text_at = self.text + self.REVERSE[(name, "KEY_LEFTSHIFT" in self.down)], self.clock()
                if self.on_type:
                    self.on_type(self)
            return
        if name == "KEY_X" and {"KEY_LEFTALT", "KEY_RIGHTSHIFT"} <= self.down:   # the camera turns: focus to the map
            self.map_focus, self.panel = True, 0
            return
        if name == "KEY_2" and {"KEY_RIGHTALT", "KEY_COMPOSE"} <= self.down:   # the camera zooms: focus to the map too
            self.map_focus, self.panel = True, 0
            return
        if self.found is not None and (self.map_focus or self.panel):   # the system panel of the found system
            if name == "KEY_D":   # the column is entered at its top; a Right there does nothing
                if self.panel == 1:
                    self.icon = 0
                self.panel, self.map_focus = min(2, self.panel + 1), False
                return
            if name == "KEY_S" and self.panel == 2:
                self.icon = min(12, self.icon + 1)
                return
            if name == "KEY_SPACE" and self.panel == 2:
                if self.icon == self.TARGET_ICON:
                    self.status["destination"] = {"System": self.found[1], "Body": 0, "Name": self.found[0]}
                    self.fsd.append(self.found[1])
                    if self.target_closes:   # the game may close the map once the system is targeted (2026-10-23)
                        self.set_focus(0)
                        if self.on_close:
                            self.on_close(self)
                return
        if name in ("KEY_D", "KEY_A"):   # into / along the tab column (Trade Routes, Bookmarks...): not the search box
            self.tab, self.search_lit = 1, False
        elif name == "KEY_W":            # straight after opening: highlights "Search the Galaxy"
            self.search_lit = self.tab == 0
        elif name == "KEY_SPACE":
            if self.search_lit and self.found is None and not self.text:   # the cursor goes into the search box
                self.focused, self.search_lit = True, False
            else:   # on its own: the current system's details (or, held after a search, plot the route)
                self.select_at = self.clock()

    def syn(self):
        pass

    def close(self):
        self.closed = True


class FakeDesktop:
    """Stands in for the X desktop behind wmctrl and xprop (outrider/game_window.py through the overlay's X11 tracker):
    its windows {id: title}, the active one, and whether `wmctrl -i -a` is obeyed (a compositor that ignores X11
    activation: obeys False). Records every command; nothing reaches a real display, window or key."""
    GAME, BROWSER = 0x3c00007, 0x2a00003

    def __init__(self, windows=None, active=None, obeys=True):
        self.windows = dict(windows) if windows is not None else {
            self.GAME: "Elite - Dangerous (CLIENT)", self.BROWSER: "ED Outrider \u2014 Mozilla Firefox"}
        self.active = self.BROWSER if active is None else active
        self.obeys, self.calls = obeys, []

    def run(self, cmd, **_kw):
        import types
        self.calls.append(list(cmd))
        out = ""
        if cmd[:2] == ["wmctrl", "-lGx"]:
            out = "".join(f"0x{i:08x}  0 0 0 1920 1080 steam_app_359320.steam_app_359320  host {t}\n"
                          for i, t in self.windows.items())
        elif cmd[:2] == ["xprop", "-root"]:
            out = f"_NET_ACTIVE_WINDOW(WINDOW): window id # 0x{self.active:x}\n"
        elif cmd[:3] == ["wmctrl", "-i", "-a"] and self.obeys and int(cmd[3], 16) in self.windows:
            self.active = int(cmd[3], 16)
        return types.SimpleNamespace(returncode=0, stdout=out, stderr="")

    def activations(self):
        return [c[3] for c in self.calls if c[:3] == ["wmctrl", "-i", "-a"]]

    def window(self, tools=("wmctrl", "xprop"), **kw):
        """A GameWindow on this desktop (Linux, a display, the tools given installed)."""
        import outrider.game_window
        return outrider.game_window.GameWindow(platform="linux", run=self.run, environ={"DISPLAY": ":0"},
                                               which=lambda t: f"/usr/bin/{t}" if t in tools else None, **kw)


def outrider_honk():
    import outrider.honk
    return outrider.honk


# shared from BioRules.M_SYSTEM (an alias there)
BIO_M_SYSTEM = {"x": -3485, "y": 39, "z": 7320, "stars": [{"type": "M", "luminosity": "Va", "main": True}],
            "planet_types": ["Rocky body", "Icy body"]}


# shared from Batch2Values.CANDS (an alias there)
CANDS = [{"name": "Stratum Tectonicas", "genus": "Stratum", "value": 19_010_800},
         {"name": "Concha Biconcavis", "genus": "Concha", "value": 16_777_215},
         {"name": "Fungoida Bullarum", "genus": "Fungoida", "value": 3_703_200},
         {"name": "Bacterium Aurasus", "genus": "Bacterium", "value": 1_000_000}]


# shared from Batch6Voice.organic (an alias there)
def voice_organic(self, ts, kind, species="Stratum Tectonicas", genus="Stratum"):
    self.j.handle({"event": "ScanOrganic", "timestamp": ts, "ScanType": kind, "SystemAddress": 1, "Body": 4,
                   "Genus": f"$Codex_Ent_{genus}_Genus_Name;", "Genus_Localised": genus,
                   "Species": f"$Codex_Ent_{species.replace(' ', '_')}_Name;", "Species_Localised": species})


# shared from Batch6Voice.sampling_body (an alias there)
def voice_sampling_body(self):
    self.planet("2026-01-01T00:01:00Z", 1, 4, "A 4", Landable=True, SurfaceGravity=2.6 * 9.80665, WasFootfalled=False,
                AtmosphereType="CarbonDioxide", SurfaceTemperature=180, PlanetClass="Rocky body", MassEM=0.2)
    self.j.handle({"event": "SAASignalsFound", "timestamp": "2026-01-01T00:02:00Z", "SystemAddress": 1, "BodyName": "S1 A 4",
                   "BodyID": 4, "Signals": [{"Type": ed_outrider.BIO, "Count": 2}],
                   "Genuses": [{"Genus": "$Codex_Ent_Stratum_Genus_Name;", "Genus_Localised": "Stratum"},
                               {"Genus": "$Codex_Ent_Bacterial_Genus_Name;", "Genus_Localised": "Bacterium"}]})


# shared from Batch6Voice.moments (an alias there)
def voice_moments(self, kind):
    self.db.commit()
    return [m for m in self.state.moments_summary() if m["kind"] == kind]


# shared from Batch6Voice.planet (an alias there)
def voice_planet(self, ts, id64, body_id, name, **kw):
    ev = scan(ts, f"S{id64}", id64, body_id, f"S{id64} {name}")[2]
    ev.update(kw)
    self.j.handle(ev)


# shared from Batch6Voice.honk (an alias there)
def voice_honk(self, ts, id64, count, progress=0.2):
    self.j.handle({"event": "FSSDiscoveryScan", "timestamp": ts, "SystemName": f"S{id64}", "SystemAddress": id64,
                   "BodyCount": count, "Progress": progress})


# shared from Batch6Voice.jump (an alias there)
def voice_jump(self, ts, id64, x):
    self.j.handle({"event": "FSDJump", "timestamp": ts, "StarSystem": f"S{id64}", "SystemAddress": id64, "StarPos": [x, 0, 0]})


# shared from BatchBVoiceControl.fake_evdev (an alias there)
def button_fake_evdev(self, script):
    """A stand-in for the evdev module: one device ("Saitek X-56 Throttle") whose events come from `script`
    (a list of (seconds to wait, value) for the button, then an OSError, as an unplug gives). grab() and any
    virtual device fail the test."""
    import types
    test = self

    class Ev:
        def __init__(self, value, code=300, type_=1):
            self.type, self.code, self.value = type_, code, value

    class Dev:
        opened = []

        def __init__(self, path):
            if path == "/dev/input/event9":
                raise PermissionError(13, "Permission denied")
            self.path, self.closed = path, False
            self.name = "Saitek X-56 Throttle" if path.endswith("5") else "Saitek X-56 Stick" if path.endswith("4") else "Keyboard"
            Dev.opened.append(self)

        def capabilities(self):   # the throttle has the button (300); the stick, listed first, does not
            return {1: [300, 301]} if self.path.endswith("5") else {1: [288]}

        def grab(self):
            test.fail("the button must never grab the device")

        def close(self):
            self.closed = True

        async def async_read_loop(self):
            import asyncio
            for wait, value in script:
                await asyncio.sleep(wait)
                yield Ev(value, code=1, type_=0)   # noise: another event type
                yield Ev(value, code=301)          # another button
                yield Ev(value)
            raise OSError(19, "No such device")

    def uinput(*a, **k):
        test.fail("the button must never create a virtual device")
    ecodes = types.SimpleNamespace(EV_KEY=1, ecodes={"BTN_TRIGGER_HAPPY5": 300, "KEY_F13": 183},
                                   BTN={300: "BTN_TRIGGER_HAPPY5"}, KEY={183: "KEY_F13"})
    return types.SimpleNamespace(ecodes=ecodes, InputDevice=Dev, UInput=uinput,
                                 list_devices=lambda: ["/dev/input/event3", "/dev/input/event4", "/dev/input/event5",
                                                       "/dev/input/event9"]), Dev


# shared from BatchDFuel.MANDALAY_JUMPS (an alias there)
MANDALAY_JUMPS = [[1.177, 0.000179, 31.999821, 0], [1.875, 0.000559, 30.999441, 0], [2.791, 0.001483, 31.498516, 0],
                  [3.295, 0.002229, 31.490419, 0], [3.914, 0.003346, 28.849634, 0], [4.245, 0.004158, 31.995842, 0],
                  [4.663, 0.005234, 31.994766, 0], [4.878, 0.005739, 28.935785, 0], [5.252, 0.006984, 31.477118, 0],
                  [5.985, 0.00962, 31.490379, 0], [7.012, 0.014219, 31.985781, 0], [12.441, 0.057825, 31.56846, 0]]


# shared from BatchDFuel.MANDALAY (an alias there)
MANDALAY = {"unladen": 323.150024, "max_range": 83.487473, "fsd_size": 5, "booster_ly": 10.5, "max_fuel": None}


# shared from HighwayH1.plot_exact (an alias there)
def hwy_plot_exact(self, start=-100):
    """The fixture route stored as a finished plot, you at its start (arrived `start` s ago)."""
    self.jump(start, 100, "Start", 0)
    rows = ed_outrider.highway_rows("exact", self.EXACT)
    return self.state.highway_store(rows, {"plotter": "exact", "options": {}, "ship": None})


# shared from HighwayH1.jump (an alias there)
def hwy_jump(self, s, id64, name, x, kind="FSDJump"):
    self.j.handle({"event": kind, "timestamp": self.ts(s) if isinstance(s, (int, float)) else s, "StarSystem": name,
                   "SystemAddress": id64, "StarPos": [x, 0, 0]})


# shared from HighwayH1.ts (an alias there)
def hwy_ts(self, s):
    return ed_outrider.iso_ts(self.now + s)


# shared from HighwayH1.EXACT (an alias there)
HWY_EXACT = {"jumps": [
    {"name": "Start", "id64": 100, "x": 0, "y": 0, "z": 0, "distance": 0, "distance_to_destination": 200,
     "fuel_used": 0, "fuel_in_tank": 32, "must_refuel": 0, "has_neutron": True},
    {"name": "Neu A", "id64": 101, "x": 50, "y": 0, "z": 0, "distance": 50, "distance_to_destination": 150,
     "fuel_used": 5.1, "fuel_in_tank": 26.9, "must_refuel": 0, "has_neutron": True},
    {"name": "Bridge B", "id64": 102, "x": 80, "y": 0, "z": 0, "distance": 30, "distance_to_destination": 120,
     "fuel_used": 3.2, "fuel_in_tank": 23.7, "must_refuel": 0, "has_neutron": False},
    {"name": "Scoop C", "id64": 103, "x": 100, "y": 0, "z": 0, "distance": 20, "distance_to_destination": 100,
     "fuel_used": 2.0, "fuel_in_tank": 21.7, "must_refuel": 1, "has_neutron": False},
    {"name": "Neu D", "id64": 104, "x": 150, "y": 0, "z": 0, "distance": 50, "distance_to_destination": 50,
     "fuel_used": 5.0, "fuel_in_tank": 27.0, "must_refuel": 0, "has_neutron": True},
    {"name": "End", "id64": 105, "x": 200, "y": 0, "z": 0, "distance": 50, "distance_to_destination": 0,
     "fuel_used": 5.0, "fuel_in_tank": 22.0, "must_refuel": 0, "has_neutron": False}]}


# shared from Batch0Security.guard (an alias there)
def guard_status(self, method, host, origin=None, site=None, allowed=None, path="/api/autohonk/test"):
    """Status the request guard gives a request (200: it reached the handler)."""
    import asyncio
    from aiohttp import web
    from aiohttp.test_utils import make_mocked_request
    headers = {"Host": host}
    if origin:
        headers["Origin"] = origin
    if site:
        headers["Sec-Fetch-Site"] = site
    allowed = ed_outrider.allowed_hosts("127.0.0.1", 8025) if allowed is None else allowed

    async def handler(_):
        return web.Response(text="ok")

    async def go():
        return (await ed_outrider.request_guard(allowed)(make_mocked_request(method, path, headers=headers),
                                                         handler)).status
    return asyncio.run(go())


# shared from Batch5ConfigCli.controls (an alias there)
def make_controls(self, root, start="My X56\nMy X56\nMy X56\nMy X56"):
    journals = os.path.join(root, "steamuser", "Saved Games", "Frontier Developments", "Elite Dangerous")
    binds = os.path.join(root, "steamuser", "AppData", "Local", "Frontier Developments", "Elite Dangerous",
                         "Options", "Bindings")
    os.makedirs(journals, exist_ok=True)
    os.makedirs(binds, exist_ok=True)
    if start is not None:
        with open(os.path.join(binds, "StartPreset.4.start"), "w") as f:
            f.write(start)
    return journals, binds


class FakeClock:
    """Time that moves only when the code under test waits: wait(secs) and sleep(secs) advance it at once, so a run
    of outrider.target's Targeter takes no real time. at(delay, fn) calls fn once the clock has passed delay seconds
    from now (an event arriving late). Install it with `use_fake_time(targeter, game)`."""

    def __init__(self, start=1000.0, cancel=None, cancelled=None):
        self.t, self.due = float(start), []
        # an Event, or a callable (Targeter.cancelled: shutdown or the run's own token)
        self.cancelled = cancelled or ((lambda: cancel.is_set()) if cancel is not None else (lambda: False))

    def __call__(self):
        return self.t

    def at(self, delay, fn):
        self.due.append((self.t + delay, fn))
        self.due.sort(key=lambda d: d[0])

    def sleep(self, secs):
        self.t += max(0.0, float(secs or 0))
        while self.due and self.due[0][0] <= self.t:
            self.due.pop(0)[1]()

    def wait(self, secs):
        """An interruptible pause, like threading.Event.wait: True when cancelled."""
        if self.cancelled():
            return True
        self.sleep(secs)
        return bool(self.cancelled())


def use_fake_time(targeter, game=None):
    """Run a Targeter (and the FakeGame behind it) on a FakeClock; returns the clock."""
    clock = FakeClock(cancelled=targeter.cancelled)
    targeter.clock, targeter.wait, targeter.sleep = clock, clock.wait, clock.sleep
    if game is not None:
        game.clock = clock
    return clock
