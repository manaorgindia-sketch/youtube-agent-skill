"""One test per bug fixed on feature/telugu-support. Each names the bug it guards."""
import json, os, re, shutil, tempfile, unittest
from helpers import ROOT, SKILLS, TOOLS, fx, run, run_json, tool
import textutil as T
import hooks as H


class Title(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.m = tool("title")

    def test_telugu_thumbnail_duplicate_is_caught(self):
        # bug: [a-z0-9'] dropped Telugu, so this "carried different words"
        r = self.m.check("మీ డబ్బు ఎలా పోయింది", "మీ డబ్బులు పోయాయి")
        self.assertIn("duplicate", [k for k, _ in r["issues"]])
        self.assertIn("డబ్బు", dict(r["issues"])["duplicate"])

    def test_telugu_title_is_not_flagged_front_load(self):
        r = self.m.check("మీ డబ్బు ఎలా పోయింది")
        self.assertNotIn("front-load", [k for k, _ in r["issues"]])

    def test_digit_free_amount_counts_as_a_figure(self):
        r = self.m.check("కోటి రూపాయలు పోగొట్టుకున్న రైతు")
        self.assertNotIn("no-number", [k for k, _ in r["issues"]])

    def test_telugu_vague_word(self):
        r = self.m.check("సంచలనం! అద్భుతమైన షాకింగ్ నిజం")
        self.assertIn("vague", [k for k, _ in r["issues"]])

    def test_truncation_uses_visible_characters(self):
        t = "ఈ ఒక్క తప్పుతో కోటి రూపాయలు పోగొట్టుకున్న రైతు కథ: ప్రభుత్వ పథకం గురించి మీకు తెలియని నిజాలు ఇవే"
        r = self.m.check(t)
        self.assertGreater(r["chars"], 90)                      # typed characters, for the 100 limit
        self.assertNotIn("length", [k for k, _ in r["issues"]])  # ~56 visible, inside the desktop cut
        self.assertIn("mobile", [k for k, _ in r["issues"]])

    def test_english_unchanged(self):
        r = self.m.check("Why Your Thumbnails Are Losing You Views", "LOSING VIEWS")
        self.assertIn("duplicate", [k for k, _ in r["issues"]])


class Hookscore(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.m = tool("hookscore")

    def test_telugu_hook_is_read(self):
        # bug: scored 30/WEAK - 0 words, no address, no stakes, no amount
        parts, verdict, _, _ = self.m.score("మీరు ఈ ఒక్క తప్పు చేస్తే రూ. 10 లక్షలు పోగొట్టుకుంటారు. ఎందుకు అని చాలామందికి తెలియదు")
        self.assertGreaterEqual(parts["ADDRESS"], 76)
        self.assertGreaterEqual(parts["STAKES"], 48)
        self.assertGreater(parts["CURIOSITY"], 24)
        self.assertEqual(parts["BREVITY"], 100)
        self.assertGreaterEqual(verdict, 55)

    def test_weak_telugu_hook_stays_weak(self):
        _, verdict, _, _ = self.m.score("నమస్కారం ఫ్రెండ్స్ ఈరోజు వీడియో లో ఒక అద్భుతం చూద్దాం")
        self.assertLess(verdict, 55)

    def test_dollar_amount_counted_once(self):
        # bug: \b\$\d could never match; the fix must not double-count "$500"
        self.assertEqual(len(self.m.CONCRETE.findall("costs $500 a month")), 1)

    def test_sentence_final_vague_word(self):
        # bug: "insane." kept its full stop and never matched VAGUE
        self.assertEqual(self.m.specificity("This is insane."), 18)

    def test_decimal_is_one_word(self):
        self.assertEqual(len(self.m.words("grew 3.5x in 1,000 days")), 5)


class Deadair(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.m = tool("deadair")

    def test_numbers_make_different_sentences(self):
        # bug: digits were stripped, so 2024/2025 read as a retake
        self.assertFalse(self.m.is_restart("In 2024 we lost 40 percent", "In 2025 we lost 10 percent"))

    def test_short_abandoned_take_is_a_restart(self):
        self.assertTrue(self.m.is_restart("So today we look", "So today we look at retention"))
        self.assertTrue(self.m.is_restart("మీరు ఈ విషయం తెలుసుకోవాలి",
                                          "మీరు ఈ విషయం తెలుసుకోవాలి ఎందుకంటే గడువు దగ్గర పడింది"))

    def test_two_word_opening_is_not_enough(self):
        self.assertFalse(self.m.is_restart("So today", "So today we start"))

    def test_overlapping_cuts_counted_once(self):
        cuts = [{"start": 0, "end": 2}, {"start": 1, "end": 3}, {"start": 5, "end": 6}]
        self.assertEqual(self.m.covered(cuts), 4)

    def test_telugu_transcript(self):
        cues = T.load(fx("te", "talk.srt"))
        cuts, _ = self.m.edl(cues)
        kinds = [(c["kind"], c["start"]) for c in cuts]
        fillers = [c["why"] for c in cuts if c["kind"] == "FILLER"]
        self.assertEqual(fillers, ["అంటే", "సరే", "మరి"])
        repeats = [c for c in cuts if c["kind"] == "REPEAT"]
        self.assertEqual(len(repeats), 1, kinds)              # the abandoned take, not the 2024/2025 pair
        self.assertEqual(repeats[0]["start"], cues[3][0])
        self.assertEqual(sum(1 for c in cuts if c["kind"] == "DEAD"), 3)

    def test_mixed_transcript_and_romanized_flag(self):
        cues = T.load(fx("mixed", "talk.srt"))
        plain = [c["why"] for c in self.m.edl(cues)[0] if c["kind"] == "FILLER"]
        roman = [c["why"] for c in self.m.edl(cues, romanized=True)[0] if c["kind"] == "FILLER"]
        self.assertEqual(plain, ["um", "so yeah"])
        self.assertEqual(roman, ["um", "so yeah", "ante"])
        self.assertEqual([c["kind"] for c in self.m.edl(cues)[0]].count("REPEAT"), 1)


class Retention(unittest.TestCase):
    def test_flags_in_any_order(self):
        # bug: "--duration 600 file.csv" took 600 as the file name
        a = run_json("retention", "--duration", "600", fx("en", "pct.csv"))
        b = run_json("retention", fx("en", "pct.csv"), "--duration", "600")
        self.assertEqual(a, b)

    def test_short_on_seconds_axis(self):
        # bug: any series under 100 was read as percent - a 60s Short reported 9% instead of 30%
        out = run_json("retention", fx("te", "short_seconds.csv"))
        self.assertEqual(out["axis"], "seconds")
        self.assertEqual(out["hook_leak"], 30.0)

    def test_axis_override(self):
        out = run_json("retention", fx("te", "short_seconds.csv"), "--axis", "percent")
        self.assertEqual(out["axis"], "percent")
        self.assertEqual(out["axis_from"], "--axis")

    def test_telugu_header_percent(self):
        out = run_json("retention", fx("te", "retention_pct.csv"), "--duration", "300")
        self.assertEqual((out["axis"], out["axis_from"]), ("percent", "header"))

    def test_detect_axis(self):
        d = tool("retention").detect_axis
        self.assertEqual(d([0, 50, 590])[0], "seconds")
        self.assertEqual(d([0, 50, 100])[0], "percent")
        self.assertEqual(d([0, 30, 57])[0], "seconds")
        self.assertEqual(d([0, 30, 57], duration=58)[0], "seconds")
        self.assertEqual(d([0, 50, 100], duration=58)[0], "percent")
        self.assertEqual(d([0, 50, 98], header=["Video position (seconds)"])[0], "seconds")


class HooksJson(unittest.TestCase):
    def test_no_identical_pattern_in_two_formulas(self):
        # Exact duplicates only. The \bstop\b overlap (different text, same trigger) is guarded by
        # SharedClassifier.test_stop_is_the_mistake.
        seen = {}
        for f in H.load_formulas():
            for p in f["match"]:
                self.assertNotIn(p, seen, f"{p} in {seen.get(p)} and {f['name']}")
                seen[p] = f["name"]

    def test_no_repeated_alternatives(self):
        # bug: analys(ed|ed|is|e)
        for f in H.load_formulas():
            for p in f["match"]:
                for group in re.findall(r"\(([^()?]*)\)", p):
                    alts = group.split("|")
                    self.assertEqual(len(alts), len(set(alts)), f"{f['name']}: {p}")

    def test_patterns_compile(self):
        for f in H.load_formulas():
            for p in f["match"] + f.get("match_te", []): re.compile(p)


class SharedClassifier(unittest.TestCase):
    def test_hookscore_and_swipe_agree(self):
        # bug: hookscore kept the first top formula, swipe the alphabetically last name
        hs, sw = tool("hookscore"), tool("swipe")
        lines = []
        for p in [fx("en", "hooks.txt"), fx("en", "titles.txt"), fx("te", "hooks.txt"), fx("mixed", "hooks.txt")]:
            with open(p, encoding="utf-8") as fh:
                lines += [l for l in fh.read().splitlines() if l.strip()]
        lines += ["Stop doing this before you upload"]
        for l in lines:
            self.assertEqual(hs.classify(l)[0], sw.classify(l), l)

    def test_stop_is_the_mistake(self):
        self.assertEqual(tool("swipe").classify("Stop doing this"), "The Mistake")


class Swipe(unittest.TestCase):
    def test_parse_views(self):
        pv = tool("swipe").parse_views
        cases = {412000: 412000, "412,000": 412000, "1.2M": 1.2e6, "45K": 45000, "12 లక్షలు": 1.2e6,
                 "1.5 crore": 1.5e7, "50,000 views": 50000, "2 కోట్లు": 2e7, None: 0, "": 0}
        for v, want in cases.items(): self.assertAlmostEqual(pv(v), want, msg=repr(v))
        self.assertIsNone(pv("???"))

    def test_telugu_collection(self):
        p = run("swipe", fx("te", "collected.json"), "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)
        self.assertEqual(out["outliers"][0]["views"], 1_200_000)
        self.assertEqual(out["outliers"][0]["formula"], "The Question")
        self.assertIn("unreadable", p.stderr)


class Chapters(unittest.TestCase):
    def test_draft_titles_are_deterministic(self):
        # bug: tie order came from a set, so titles changed with PYTHONHASHSEED
        outs = {run("chapters", fx("en", "talk.srt"), env={"PYTHONHASHSEED": s}).stdout for s in ("1", "2", "3")}
        self.assertEqual(len(outs), 1)

    def test_telugu_keywords_drive_titles(self):
        out = run_json("chapters", fx("te", "talk.srt"))
        titles = " ".join(c["draft_title"] for c in out["chapters"])
        self.assertTrue(out["valid"])
        self.assertNotIn("Section", titles)
        self.assertIn("దరఖాస్తు", titles)


class Encoding(unittest.TestCase):
    def test_telugu_on_a_non_utf8_console(self):
        # bug: open() without encoding= and cp1252 stdout broke Telugu on Windows, Python < 3.15
        for name, arg in [("title", fx("te", "titles.txt")), ("hookscore", fx("te", "hooks.txt"))]:
            p = run(name, arg, env={"PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252"})
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("డబ్బు" if name == "title" else "మీరు", p.stdout)

    def test_json_is_not_escaped(self):
        p = run("hookscore", "--hook", "మీరు తెలుసుకోవాలి", "--json")
        self.assertIn("మీరు", p.stdout)
        self.assertNotIn("\\u0c", p.stdout)


class Packaging(unittest.TestCase):
    def test_a_tool_copied_alone_fails_clearly(self):
        d = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(d, "yt-edit"))
            shutil.copy(TOOLS["deadair"], os.path.join(d, "yt-edit"))
            p = run("deadair", "x.srt", script=os.path.join(d, "yt-edit", "deadair.py"))
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("skills/_shared", p.stderr)
            self.assertNotIn("Traceback", p.stderr)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_eleven_skills_and_shared_is_not_one(self):
        skills = sorted(d for d in os.listdir(SKILLS) if os.path.exists(os.path.join(SKILLS, d, "SKILL.md")))
        self.assertEqual(len(skills), 11, skills)
        self.assertNotIn("_shared", skills)


if __name__ == "__main__":
    unittest.main()
