"""Unit tests: the documentation's links. The README is a front page and the user guide is docs/guide/ (2026-10-07):
every relative link and image must reach a file, every #anchor a heading (or an explicit <a id>) of its page, the
README must index every guide page, and each page's nav bar must link all the others. And docs/AGENT_GUIDE.md names
every route the app registers (RoutesInTheGuide).

Run all: python3 -m unittest discover tests (or scripts/verify.sh).
"""
import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def slug(heading):
    """GitHub's anchor for a heading: lower case, punctuation and emoji gone, spaces to hyphens."""
    t = re.sub(r"[^\w\- ]", "", heading.lstrip("#").strip().lower())
    return t.replace(" ", "-")


def text_of(path):
    with open(path, encoding="utf-8") as f:
        return re.sub(r"```.*?```", "", f.read(), flags=re.S)   # code blocks hold no links


def anchors(path):
    s = text_of(path)
    return {slug(line) for line in s.split("\n") if line.startswith("#")} | set(re.findall(r'<a id="([^"]+)"', s))


def doc_files():
    return [os.path.join(ROOT, "README.md")] + sorted(glob.glob(os.path.join(ROOT, "docs", "guide", "*.md"))) + \
        sorted(glob.glob(os.path.join(ROOT, "docs", "*.md")))


class DocLinks(unittest.TestCase):

    def test_relative_links_and_anchors(self):
        bad = []
        for path in doc_files():
            s = text_of(path)
            for t in re.findall(r"\]\(([^)\s]+)\)", s) + re.findall(r'(?:href|src)="([^"]+)"', s):
                if re.match(r"(https?:|mailto:)", t) or t.startswith("<"):
                    continue
                target, _, frag = t.partition("#")
                dest = os.path.normpath(os.path.join(os.path.dirname(path), target)) if target else path
                where = os.path.relpath(path, ROOT)
                if not os.path.exists(dest):
                    bad.append(f"{where}: no file {t}")
                elif frag and dest.endswith(".md") and frag not in anchors(dest):
                    bad.append(f"{where}: no anchor {t}")
        self.assertEqual(bad, [])

    def test_guide_index_and_nav(self):
        pages = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "docs", "guide", "*.md")))
        self.assertGreater(len(pages), 5)
        readme = text_of(os.path.join(ROOT, "README.md"))
        for p in pages:
            self.assertIn(f"](docs/guide/{p})", readme, p)
        for p in pages:
            nav = text_of(os.path.join(ROOT, "docs", "guide", p)).split("\n", 1)[0]
            self.assertIn("](../../README.md)", nav, p)
            for other in pages:
                self.assertIn(f"]({other})" if other != p else "**", nav, (p, other))

    def test_old_readme_anchors_kept(self):
        """Links into the old single README (release notes, posts) still land: its sections' anchors stay."""
        kept = anchors(os.path.join(ROOT, "README.md"))
        for old in ("-running-as-a-server-docker", "-other-devices-on-your-network", "-the-neutron-highway", "-trading",
                    "-cargo-and-your-carrier", "-auto-honk", "-on-a-tablet", "-settings", "-the-voice", "-getting-started"):
            self.assertIn(old, kept)


# ---- Every route in the agent guide (NEXT-VERSION #11) ----

ADD_CALL = re.compile(r"\.router\.add_(?:get|post|route|static)\(")
ADD_PATH = re.compile(r'\.router\.add_(?:get|post|route|static)\(\s*(?:"[A-Z*]+",\s*)?(f?)"([^"]+)"')
# The one loop of make_app: `for part, fn in (("profile", ...), ...): app.router.add_get(f"/api/commander/{part}", ...)`
COMMANDER_LOOP = re.compile(r'for part, fn in \((.*?)\):.*?add_get\(f"/api/commander/\{part\}"', re.S)
COMMANDER_PATH = "/api/commander/{part}"


def make_app_source():
    """ed_outrider.py's make_app, from its def to the next top-level def or class."""
    with open(os.path.join(ROOT, "ed_outrider.py"), encoding="utf-8") as f:
        src = f.read()
    start = src.index("\ndef make_app(")
    end = re.compile(r"\n(?:def|class|async def) ").search(src, start + 1).start()
    return src[start:end]


def registered_routes(source):
    """(paths, commander parts): every path make_app registers, as written, and the parts of the Commander loop. The
    loop's f-string is the parameterised path `/api/commander/{part}`; any other f-string path, or an add_* call whose
    path this cannot read, raises, so a new kind of registration is handled here rather than skipped."""
    found = ADD_PATH.findall(source)
    if len(found) != len(ADD_CALL.findall(source)):
        raise ValueError("an app.router.add_* call whose path is not a string literal: read it here explicitly")
    paths, parts = [], []
    for is_f, path in found:
        if is_f and path != COMMANDER_PATH:
            raise ValueError(f"a new f-string route {path!r}: expand it here explicitly")
        paths.append(path)
    if COMMANDER_PATH in paths:
        loop = COMMANDER_LOOP.search(source)
        if not loop:
            raise ValueError("the Commander loop changed shape: read its parts here explicitly")
        parts = re.findall(r'\(\s*"(\w+)"\s*,', loop.group(1))
        if not parts:
            raise ValueError("no parts read from the Commander loop")
    return paths, parts


def norm_path(text):
    """A placeholder segment, `{name}`, `{name:regex}` or the prose's `<name>`, as `{}`."""
    return re.sub(r"\{[^}/]*\}|<[^>/\s]*>", "{}", text)


def named_in(path, text):
    """Whether `text` (a guide) names the registered `path`; see RoutesInTheGuide for the rule."""
    p, t = norm_path(path), norm_path(text)
    if re.search(r"(?<![\w.\-/])" + re.escape(p) + r"(?![\w\-/*]|\.\w)", t):
        return True
    return any(p.startswith(fam + "/") for fam in re.findall(r"(?<![\w.\-/])(/[\w\-/{}.]*?)/\*(?![\w/*])", t))


class RoutesInTheGuide(unittest.TestCase):
    """Every route make_app registers is named in docs/AGENT_GUIDE.md (NEXT-VERSION #11: about 20 older routes had gone
    unnamed). The routes are read from ed_outrider.py's source, make_app only (the starting app's few are in its own
    entry): every app.router.add_get / add_post / add_route / add_static call's path, the Commander loop's f-string
    taken as `/api/commander/{part}` (`registered_routes` refuses any registration it cannot read).

    The rule for "named" (`named_in`):
    - A placeholder segment is normalised on both sides: `{id64}`, `{name:regex}` and the guide's `<part>` all read `{}`,
      so `/api/system/{id64}` is named by `/api/system/{id64}` or `/api/system/<id64>`.
    - The whole path must appear: not preceded by a path character (a letter, digit, `_`, `-`, `.`, `/`) and not
      followed by one (a letter, digit, `_`, `-`, `/`, `*`, or `.` then a letter). So `/api/status.txt` does not name
      `/api/status`, `/api/say/play` does not name `/api/say`, and `/api/rail*` names nothing; a query (`?q=`), a
      backtick, a space or punctuation may follow.
    - A family may be named by its prefix only as `<prefix>/*` (a slash and a star, nothing after): it covers every
      registered path strictly under the prefix, never the prefix itself.
    - A relative shorthand ("`/api/highway` (+ `/systems`)") names nothing: each path is written whole somewhere.
    - The Commander loop's parts: the guide line naming `/api/commander/<part>` must also name each part, backticked,
      so a part added to the loop is documented too."""

    def setUp(self):
        with open(os.path.join(ROOT, "docs", "AGENT_GUIDE.md"), encoding="utf-8") as f:
            self.guide = f.read()

    def test_the_rule(self):
        self.assertTrue(named_in("/api/x", "POST `/api/x` {id}: ..."))
        self.assertTrue(named_in("/api/x", "GET `/api/x?q=` and"))
        self.assertTrue(named_in("/api/system/{id64}", "`/api/system/<id64>`"))
        self.assertTrue(named_in("/api/commander/{part}", "GET `/api/commander/<part>`"))
        self.assertTrue(named_in("/static/", "for `/api/`, `/static/` and"))
        self.assertFalse(named_in("/api/status", "`/api/status.txt`"))
        self.assertTrue(named_in("/api/status", "`/api/status`."))
        self.assertFalse(named_in("/api/say", "`/api/say/play`"))
        self.assertFalse(named_in("/api/x/y", "`/api/x` (+ `/y`)"))
        self.assertFalse(named_in("/api/x", "`api/x`"))
        self.assertFalse(named_in("/api/x", "`/v2/api/x`"))
        self.assertTrue(named_in("/api/rail/press", "`/api/rail/*`"))
        self.assertTrue(named_in("/api/rail/sets/x", "`/api/rail/*`"))
        self.assertFalse(named_in("/api/rail", "`/api/rail/*`"))
        self.assertFalse(named_in("/api/rail", "`/api/rail*`"))
        self.assertFalse(named_in("/api/rail/press", "`/api/rail*`"))
        self.assertFalse(named_in("/api/railway", "`/api/rail/*`"))

    def test_registrations_read(self):
        src = make_app_source()
        paths, parts = registered_routes(src)
        self.assertGreater(len(paths), 100)
        self.assertIn("/api/nearby", paths)
        self.assertIn("/static/", paths)
        self.assertEqual(parts, ["profile", "inventory", "engineering", "missions", "sessions"])
        with self.assertRaises(ValueError):
            registered_routes(src + '\n    app.router.add_get(f"/api/x/{k}", h)')
        with self.assertRaises(ValueError):
            registered_routes(src + "\n    app.router.add_get(PATH, h)")

    def test_every_route_named(self):
        paths, parts = registered_routes(make_app_source())
        missing = sorted({p for p in paths if not named_in(p, self.guide)})
        self.assertEqual(missing, [], "routes docs/AGENT_GUIDE.md never names")
        lines = [ln for ln in self.guide.split("\n") if "/api/commander/<part>" in ln]
        self.assertTrue(lines)
        self.assertEqual([p for p in parts if not any(f"`{p}`" in ln for ln in lines)], [],
                         "Commander parts the /api/commander/<part> line does not list")


class Wording(unittest.TestCase):
    def read(self, *parts):
        with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
            return f.read()

    def test_requirements_is_never_edited(self):
        """Complete review 2026-10-30: the guide said to leave optional lines out of requirements.txt, a tracked file,
        and an edited one stops the guide's own `git pull` update (the launcher skips one that will not install)."""
        for path in (("docs", "guide", "install.md"), ("docs", "AGENT_GUIDE.md")):
            text = self.read(*path)
            self.assertNotIn("leave any of those lines out", text)
            self.assertNotIn("delete their lines", text)
        self.assertIn("git checkout --\nrequirements.txt", self.read("docs", "guide", "install.md"))

    def test_search_hint_follows_the_radius(self):
        """Complete review 2026-10-30: the Search hint said "passed within 25 ly" whatever the Nearby radius."""
        self.assertNotIn("passed within 25 ly", self.read("static", "page.html"))



if __name__ == "__main__":
    unittest.main()
