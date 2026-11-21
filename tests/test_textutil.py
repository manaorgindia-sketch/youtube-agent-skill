"""Unit tests for skills/_shared/textutil.py and skills/_shared/hooks.py."""
import json, os, tempfile, unittest
import helpers  # noqa: F401  (puts skills/_shared on sys.path)
import textutil as T
import hooks as H


class Tokens(unittest.TestCase):
    def test_telugu_words_stay_whole(self):
        self.assertEqual(T.tokens("మీరు ఎందుకు డబ్బు పోగొట్టుకుంటున్నారు"),
                         ["మీరు", "ఎందుకు", "డబ్బు", "పోగొట్టుకుంటున్నారు"])

    def test_mixed_and_english(self):
        self.assertEqual(T.tokens("ఈ AI tool మీకు useful, don't miss!"),
                         ["ఈ", "ai", "tool", "మీకు", "useful", "don't", "miss"])

    def test_curly_apostrophe_and_zwnj(self):
        self.assertEqual(T.tokens("You’re online ఆన్‌లైన్"), ["you're", "online", "ఆన్‌లైన్"])

    def test_word_count(self):
        self.assertEqual(T.word_count("మీ డబ్బు 5 లక్షలు ఎలా పోయింది"), 6)
        self.assertEqual(T.word_count("   "), 0)

    def test_nfc(self):
        decomposed = "ై"   # ె + ౖ, canonically ై
        self.assertEqual(T.normalize("క" + decomposed), "కై")


class Clusters(unittest.TestCase):
    def test_conjunct_is_one(self):
        self.assertEqual(T.graphemes("క్క"), 1)
        self.assertEqual(T.graphemes("మీ డబ్బు"), 4)          # మీ, space, డ, బ్బు

    def test_ascii_unchanged(self):
        s = "Why Your Thumbnails Are Losing You Views"
        self.assertEqual(T.graphemes(s), len(s))

    def test_clusters_rejoin(self):
        s = "రైతు భరోసా పథకం"
        self.assertEqual("".join(T.clusters(s)), T.normalize(s))


class Script(unittest.TestCase):
    def test_script_of(self):
        self.assertEqual(T.script_of("మీరు"), "te")
        self.assertEqual(T.script_of("tool"), "latin")
        self.assertEqual(T.script_of("2025"), "num")
        self.assertEqual(T.script_of("౧౦"), "num")

    def test_lang_mix(self):
        m = T.lang_mix("ఈ AI tool మీకు చాలా useful")
        self.assertEqual((m["te"], m["latin"], m["dominant"]), (3, 3, "te"))
        self.assertIsNone(T.lang_mix("123")["dominant"])


class Fillers(unittest.TestCase):
    def test_english(self):
        for t in ["um", "Um.", "uh, so", "so yeah", "you know, basically", "hold on", "okay right"]:
            self.assertTrue(T.is_filler_only(t), t)

    def test_telugu(self):
        for t in ["అంటే", "సరే సరే", "ఆ... అంటే", "మరి", "కదా", "ఆఁ", "హాహా"]:
            self.assertTrue(T.is_filler_only(t), t)

    def test_real_words_are_never_filler(self):
        for t in ["అది ముఖ్యం", "right now", "so the plan", "umbrella", "you know what", ""]:
            self.assertFalse(T.is_filler_only(t), t)

    def test_romanized_is_opt_in(self):
        self.assertFalse(T.is_filler_only("ante sare"))
        self.assertTrue(T.is_filler_only("ante sare", romanized=True))


class ViewerAddress(unittest.TestCase):
    def test_telugu_forms(self):
        found = [w for _, w in T.viewer_address("మీరు ఈ పుస్తకం మీద పెట్టండి, మీకు తెలుసా? మిమ్మల్ని అడుగుతున్నా")]
        self.assertEqual(found, ["మీరు", "మీకు", "మిమ్మల్ని"])

    def test_meeda_is_not_the_viewer(self):
        self.assertEqual(T.viewer_address("పుస్తకం బల్ల మీద ఉంది మీదకు వచ్చింది"), [])

    def test_english_forms_keep_old_behaviour(self):
        self.assertEqual(len(T.viewer_address("You've seen your stats, you'll see")), 3)

    def test_positions(self):
        self.assertEqual(T.viewer_address("ఈ రోజు మీకు")[0][0], 2)


class Amounts(unittest.TestCase):
    POS = {
        "మీరు రూ. 10 లక్షలు పోగొట్టుకుంటారు": ["రూ. 10 లక్షలు"],
        "₹5 lakh loan": ["₹5 lakh"],
        "costs $400 and 2 crore rupees": ["$400", "2 crore rupees"],
        "40k views": ["40k"],
        "300 రూపాయలు": ["300 రూపాయలు"],
        "Rs.500 only": ["Rs.500"],
        "౧౦ కోట్లు": ["౧౦ కోట్లు"],
        "కోటి రూపాయలు పోయాయి": ["కోటి రూపాయలు"],
        "ఎకరాకు 12 వేల రూపాయలు": ["12 వేల రూపాయలు"],
    }
    NEG = ["50% down", "in 2024", "I am 5 ft", "the 3 best tips", "లక్ష్యం ముఖ్యం"]

    def test_positive(self):
        for t, want in self.POS.items():
            self.assertEqual(T.amounts(t), want, t)

    def test_negative(self):
        for t in self.NEG:
            self.assertEqual(T.amounts(t), [], t)

    def test_digit_free(self):
        self.assertTrue(T.has_digit_free_amount("కోటి రూపాయలు"))
        self.assertTrue(T.has_digit_free_amount("a million views"))
        self.assertFalse(T.has_digit_free_amount("₹500"))


class Transcripts(unittest.TestCase):
    def _tmp(self, name, text):
        d = tempfile.mkdtemp()
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as f: f.write(text)
        return p

    def test_srt_with_bom_and_telugu(self):
        p = self._tmp("a.srt", "﻿1\n00:00:01,000 --> 00:00:02,500\nమీరు\nరెండవ లైన్\n\n2\n00:00:03,000 --> 00:00:04,000\nok\n")
        self.assertEqual(T.load(p), [(1.0, 2.5, "మీరు రెండవ లైన్"), (3.0, 4.0, "ok")])

    def test_vtt(self):
        p = self._tmp("a.vtt", "WEBVTT\n\n00:01.000 --> 00:02.000\nhello\n")
        self.assertEqual(T.load(p), [(1.0, 2.0, "hello")])

    def test_whisper_json(self):
        p = self._tmp("a.json", json.dumps({"segments": [{"start": 0, "end": 1.5, "text": " సరే "}]}))
        self.assertEqual(T.load(p), [(0.0, 1.5, "సరే")])
        p = self._tmp("b.json", json.dumps([{"start": 0, "end": 1, "text": "x"}]))
        self.assertEqual(T.load(p), [(0.0, 1.0, "x")])

    def test_parse_ts(self):
        self.assertEqual(T.parse_ts("01:02:03,500"), 3723.5)
        self.assertEqual(T.parse_ts("02:03.25"), 123.25)

    def test_dumps_keeps_telugu_readable(self):
        self.assertIn("మీరు", T.dumps({"a": "మీరు"}))


class Classifier(unittest.TestCase):
    def test_tie_goes_to_first_listed(self):
        F = [{"name": "First", "match": ["a"]}, {"name": "Second", "match": ["a"]}]
        self.assertEqual(H.classify("a", F), ("First", 1))

    def test_more_hits_wins(self):
        F = [{"name": "One", "match": ["a"]}, {"name": "Two", "match": ["a", "b"]}]
        self.assertEqual(H.classify("a b", F), ("Two", 2))

    def test_match_te_counts(self):
        F = [{"name": "Q", "match": ["^why"], "match_te": ["^ఎందుకు"]}]
        self.assertEqual(H.classify("ఎందుకు?", F), ("Q", 1))

    def test_unclassified(self):
        self.assertEqual(H.classify("zzz", H.load_formulas()), ("Unclassified", 0))

    def test_all_21_formulas_load(self):
        self.assertEqual(len(H.load_formulas()), 21)


if __name__ == "__main__":
    unittest.main()
