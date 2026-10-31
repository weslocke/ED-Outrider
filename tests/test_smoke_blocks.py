"""tests/page_smoke.js's named blocks (the review's #2, 2026-10-27): every top-level block is labelled and guarded by
skip() with its own label, the labels are unique (JavaScript allows two siblings of one name: only this test catches
it), and a full verify can never be shrunk by an exported SMOKE_ONLY."""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SmokeBlocks(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "tests", "page_smoke.js"), encoding="utf-8") as f:
            self.lines = f.read().split("\n")

    def test_every_block_is_labelled_and_guarded(self):
        bare = [i + 1 for i, line in enumerate(self.lines) if re.match(r"^  \{(\s*//.*)?$", line)]
        self.assertEqual(bare, [], "top-level blocks with no label: write `  name: { if (skip(\"name\")) break name;`")
        heads = [line for line in self.lines if re.match(r"^  \w+: \{", line)]
        labels = []
        for line in heads:
            m = re.match(r'^  (\w+): \{ if \(skip\("(\w+)"\)\) break (\w+);', line)
            self.assertTrue(m, f"a labelled block not guarded by skip(): {line[:80]}")
            self.assertEqual(len({m.group(1), m.group(2), m.group(3)}), 1, f"its guard names another label: {line[:80]}")
            labels.append(m.group(1))
        self.assertGreater(len(labels), 150)
        self.assertEqual(len(labels), len(set(labels)), sorted({x for x in labels if labels.count(x) > 1}))

    def test_a_full_verify_ignores_an_exported_smoke_only(self):
        with open(os.path.join(ROOT, "scripts", "verify.sh"), encoding="utf-8") as f:
            sh = f.read()
        self.assertRegex(sh, r"else\n  unset SMOKE_ONLY\nfi")
        self.assertIn("not a verify PASS", sh)
        # a partial pass never exits 0, the full PASS's code (review 8)
        self.assertRegex(sh, r'if \[ -n "\$PARTIAL" \]; then\n(.*\n){1,3}  if \[ "\$FAIL" = 0 \]; then exit 3; fi\n')


@unittest.skipIf(os.environ.get("OUTRIDER_VERIFY_NESTED"), "inside the verify these tests start")
class VerifyRefuses(unittest.TestCase):
    """Complete review 2026-10-30: scripts/verify.sh refuses at once, before the unit tests, a PORT something listens on
    (the smoke test clicked and posted on another Outrider) and a Python without the dev tools (it ended in PASS with
    lint and the EDDN schema tests not run). Each run is cut off after 30 s: without the refusal it would go on to
    the unit tests (these tests skip themselves there)."""

    def verify(self, env):
        import subprocess
        import signal
        p = subprocess.Popen(["scripts/verify.sh"], cwd=ROOT, env=dict(os.environ, OUTRIDER_VERIFY_NESTED="1", **env),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        try:
            out, _ = p.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGTERM)
            out, _ = p.communicate()
            return None, out
        return p.returncode, out

    def test_a_busy_port(self):
        import socket
        s = socket.socket()
        self.addCleanup(s.close)
        s.bind(("127.0.0.1", 0))
        s.listen()
        rc, out = self.verify({"PORT": str(s.getsockname()[1])})
        self.assertEqual(rc, 1, out[-500:])
        self.assertIn("something already listens on it", out)
        self.assertNotIn("=== unit tests", out)

    def test_no_dev_tools(self):
        import shutil
        import sys
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        py = os.path.join(d, "python")   # a Python with no site-packages: no pyflakes, no jsonschema
        with open(py, "w") as f:
            f.write(f'#!/bin/sh\nexec "{sys.executable}" -S -I "$@"\n')
        os.chmod(py, 0o755)
        rc, out = self.verify({"PYTHON": py, "PATH": "/usr/bin:/bin"})
        self.assertEqual(rc, 1, out[-500:])
        self.assertRegex(out, r"FAIL: (pyflakes|jsonschema) is missing")
        self.assertNotIn("=== unit tests", out)


if __name__ == "__main__":
    unittest.main()
