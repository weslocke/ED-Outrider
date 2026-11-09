"""ED Outrider's modules (ed_outrider.py at the repository root is the program).

bio (exobiology spawn rules), button (the co-pilot button), honk (auto honk), log (journal event summaries),
materials (engineering materials), speech (the spoken alerts' words), tts (Piper speech and alert sounds) and
unsold (the unsold-data estimate). Those with a command line run as `python3 -m outrider.<name>` from the
repository root.

The folders every module finds its files in: ROOT is the repository, RESOURCES_DIR the shipped data
(bio_rules.json, mining_odds.json, speech.json) and DATA_DIR your own (the database, backups, Piper voices,
banned lines; git-ignored as a whole).
"""
import os

# CalVer, bumped with each CHANGELOG entry. The Android app reads it from /api/version (with API_VERSION, the
# native-facing contract's own number, in ed_outrider.py).
__version__ = "2026.11.08"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES_DIR = os.path.join(ROOT, "resources")
DATA_DIR = os.path.join(ROOT, "data")


def read_toml(path):
    """A TOML file read as Outrider reads its config: a BOM dropped (PowerShell's utf8 writes one; complete review
    2026-10-30: the launchers' overlay step and the MCP bridge could not read such a file). Raises OSError, or
    ValueError for a file that is not UTF-8 or not TOML (tomllib.TOMLDecodeError is a ValueError)."""
    import tomllib
    with open(path, encoding="utf-8-sig") as f:
        return tomllib.loads(f.read())
