"""End-to-end: every tool as a subprocess on English, Telugu and mixed fixtures.

The English runs are compared against tests/fixtures/en/expected/*.json, recorded from the tools
after the Telugu work and checked by hand against the pre-change output (every difference was an
intended fix). To re-record after an intended change:

    UPDATE_GOLDEN=1 python -m unittest discover -s tests

and review the diff of tests/fixtures/en/expected/ before committing it.
"""
import json, os, unittest
from helpers import fx, run, run_json

UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"

GOLDEN = {
    "hook": ("hookscore", [fx("en", "hooks.txt")]),
    "title": ("title", [fx("en", "titles.txt")]),
    "title_thumb": ("title", ["--title", "Why Your Thumbnails Are Losing You Views", "--thumb", "LOSING VIEWS"]),
    "dead": ("deadair", [fx("en", "talk.srt")]),
    "chap": ("chapters", [fx("en", "talk.srt")]),
    "ret_long": ("retention", [fx("en", "long.csv"), "--transcript", fx("en", "talk.srt")]),
    "ret_pct": ("retention", [fx("en", "pct.csv"), "--duration", "600"]),
    "swipe": ("swipe", [fx("en", "collected.json")]),
}

def _strip(obj):
    if isinstance(obj, dict): obj.pop("source", None)   # an absolute path, differs per machine
    return obj


class EnglishGolden(unittest.TestCase):
    def test_golden(self):
        for key, (name, args) in GOLDEN.items():
            with self.subTest(key):
                got = _strip(run_json(name, *args))
                path = fx("en", "expected", f"{key}.json")
                if UPDATE:
                    with open(path, "w", encoding="utf-8", newline="\n") as f:
                        json.dump(got, f, indent=1, ensure_ascii=False); f.write("\n")
                    continue
                with open(path, encoding="utf-8") as f: want = json.load(f)
                self.assertEqual(got, want, f"{key}: output changed - see tests/test_cli.py to re-record")


class TeluguAndMixedRun(unittest.TestCase):
    """Every tool exits 0 and produces readable JSON on non-English input."""
    CASES = [
        ("hookscore", [fx("te", "hooks.txt")]), ("hookscore", [fx("mixed", "hooks.txt")]),
        ("title", [fx("te", "titles.txt")]), ("title", [fx("mixed", "titles.txt")]),
        ("deadair", [fx("te", "talk.srt")]), ("deadair", [fx("mixed", "talk.srt"), "--romanized"]),
        ("chapters", [fx("te", "talk.srt")]), ("chapters", [fx("mixed", "talk.srt")]),
        ("retention", [fx("te", "retention_pct.csv"), "--duration", "300", "--transcript", fx("te", "talk.srt")]),
        ("retention", [fx("te", "short_seconds.csv"), "--transcript", fx("te", "talk.srt")]),
        ("swipe", [fx("te", "collected.json")]),
    ]

    def test_runs(self):
        for name, args in self.CASES:
            with self.subTest(f"{name} {os.path.basename(args[0])}"):
                self.assertTrue(run_json(name, *args))

    def test_text_output_too(self):
        for name, args in self.CASES:
            with self.subTest(f"{name} {os.path.basename(args[0])}"):
                p = run(name, *args)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertNotIn("Traceback", p.stderr)

    def test_retention_names_what_was_said(self):
        out = run_json("retention", fx("te", "short_seconds.csv"), "--transcript", fx("te", "talk.srt"))
        self.assertTrue(any(s.strip() for s in out["said"].values()))

    def test_mixed_hook_is_addressed(self):
        out = run_json("hookscore", fx("mixed", "hooks.txt"))
        top = {r["hook"][:12]: r for r in out}
        lose = next(r for r in out if "₹5 lakh" in r["hook"])
        self.assertGreaterEqual(lose["properties"]["ADDRESS"], 46)
        self.assertGreater(lose["properties"]["STAKES"], 22)
        self.assertTrue(top)


class Usage(unittest.TestCase):
    def test_no_args_prints_usage(self):
        for name in ("hookscore", "title", "deadair", "chapters", "retention", "swipe"):
            with self.subTest(name):
                p = run(name)
                self.assertIn(".py", p.stdout)
                self.assertNotIn("Traceback", p.stderr)


if __name__ == "__main__":
    unittest.main()
