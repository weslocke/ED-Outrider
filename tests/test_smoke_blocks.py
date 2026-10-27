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


if __name__ == "__main__":
    unittest.main()
