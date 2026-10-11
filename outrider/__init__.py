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
__version__ = "2026.10.21"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES_DIR = os.path.join(ROOT, "resources")
DATA_DIR = os.path.join(ROOT, "data")
