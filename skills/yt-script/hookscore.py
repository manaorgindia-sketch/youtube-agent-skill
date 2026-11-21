#!/usr/bin/env python3
"""hookscore.py - score a YouTube hook before you waste a take on it.

Five properties, 0-100 each, and a verdict that is 60% the mean and 40% the weakest one. The
weakest-link weighting is deliberate: a hook with four strong properties and one dead one is a hook
that leaks at the dead one, and averaging hides that.

    python3 hookscore.py hooks.txt            # one hook per line, ranked
    python3 hookscore.py --hook "one line"    # score a single hook
    python3 hookscore.py --json hooks.txt     # machine-readable

English, Telugu and mixed hooks. "మీరు / మీ / మీకు" count as address, "రూ. 10 లక్షలు" as a figure.

WHAT THIS CAN AND CANNOT TELL YOU. Measured against 74 real short-form hooks (first 15 seconds of
auto-captions, top-8 and bottom-8 by views across five channels): it separates deliberately bad
hooks from real ones well, and it separates a creator's own hits from their own misses barely at
all. Treat a low score as a reason to look again, never a high score as a promise. The Telugu
word lists are a first draft and have not been measured against real Telugu hooks yet.
"""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_shared"))
try:
    import textutil as T  # noqa: E402
    from hooks import load_formulas, classify as _classify  # noqa: E402
except ImportError:
    sys.exit("hookscore.py needs skills/_shared/ - install the whole plugin, not one skill folder")

FORMULAS = load_formulas()

FILLER = {"basically","actually","literally","just","really","very","so","kind","sort","like",
          "guys","hey","welcome","today","video","subscribe","channel",
          # Telugu (draft): "hello friends", "welcome", "today", "video", "subscribe"
          "నమస్కారం","ఫ్రెండ్స్","స్వాగతం","ఈరోజు","ఇవాళ","వీడియో","సబ్స్క్రైబ్","ఛానెల్"}
VAGUE = {"amazing","incredible","insane","crazy","huge","massive","game","changer","secret",
         "powerful","ultimate","best","revolutionary","mind","blowing","unbelievable",
         # Telugu (draft)
         "అద్భుతం","అద్భుతమైన","షాకింగ్","సంచలనం","సంచలన","భారీ","బెస్ట్","రహస్యం"}
CONCRETE = re.compile(r"(?:\$\d[\d,.]*|\b\d[\d,.]*\s?(%|k|m|x|s|h)?|\b\d+\s?(second|minute|hour|day|week|month|year)s?)\b", re.I)
STAKE = re.compile(r"\b(lose|lost|wasting|waste|quit|fail|broke|cost|risk|before|stop|never|die|dying|dead)\b", re.I)
CURIOSITY = re.compile(r"\b(why|how|what|which|until|before|but|nobody|almost|except|reason|actually)\b", re.I)
CLOSED = re.compile(r"\b(because|so that|which means)\b", re.I)
# Telugu is agglutinative, so these are word STARTS: పోగొట్టు matches పోగొట్టుకుంటారు. Draft.
STAKE_TE = re.compile(r"^(నష్ట|పోగొట్టు|జాగ్రత్త|ప్రమాద|మోసం|మోసపో|ఖర్చు|అప్పు|చనిపో|ఆపండి|ఆగండి|ముందు|ఎప్పటికీ|వదిలే)")
CURIOSITY_TE = re.compile(r"^(ఎందుకు|ఎలా|ఏమిటి|ఏంటి|ఏది|ఎవరు|ఎవరికీ|కానీ|అసలు|తెలుసా|ఎంత|నిజం)")
CLOSED_TE = re.compile(r"^(ఎందుకంటే|కాబట్టి|అందుకే)$")

def words(t):
    """Words for counting: 3.5 and 1,000 stay one word, punctuation is never a word."""
    return T.tokens(re.sub(r"(?<=\d)[.,](?=\d)", "", t))

def _te_hits(rx, t): return sum(1 for w in T.tokens(t) if rx.match(w))

def specificity(t):
    w = words(t)
    if not w: return 0
    nums = len(CONCRETE.findall(t)) + (1 if T.has_digit_free_amount(t) else 0)
    vague = sum(1 for x in w if x in VAGUE)
    filler = sum(1 for x in w if x in FILLER)
    s = 34 + nums * 22 - vague * 16 - filler * 5
    # proper nouns that are not sentence-initial read as named things (Latin script only - Telugu
    # has no capitals, so a Telugu name is not rewarded here)
    s += min(18, 6 * sum(1 for x in t.split()[1:] if x[:1].isupper()))
    return max(0, min(100, s))

def address(t):
    hits = T.viewer_address(t)
    first = 30 if any(i < 6 for i, _ in hits) else 0
    return max(0, min(100, 26 + len(hits) * 20 + first))

def stakes(t):
    n = len(STAKE.findall(t)) + _te_hits(STAKE_TE, t)
    concrete = CONCRETE.search(t) or T.amounts(t)
    return max(0, min(100, 22 + n * 26 + (14 if concrete else 0)))

def curiosity(t):
    n = len(CURIOSITY.findall(t)) + _te_hits(CURIOSITY_TE, t)
    q = 18 if t.strip().endswith("?") else 0
    # a hook that resolves itself has no gap left
    closed = -18 if (CLOSED.search(t) or _te_hits(CLOSED_TE, t)) else 0
    return max(0, min(100, 24 + n * 17 + q + closed))

def brevity(t):
    n = len(words(t))
    if n == 0: return 0
    # 9-24 words is the band a spoken hook lands in at ~150wpm inside 10 seconds. Not yet
    # recalibrated for Telugu, whose words are longer and fewer per second.
    if 9 <= n <= 24: return 100
    if n < 9:  return max(30, 100 - (9 - n) * 11)
    return max(10, 100 - (n - 24) * 7)

PROPS = [("SPECIFICITY", specificity), ("ADDRESS", address), ("STAKES", stakes),
         ("CURIOSITY", curiosity), ("BREVITY", brevity)]

def classify(t):
    return _classify(t, FORMULAS)

def score(t):
    parts = {n: fn(t) for n, fn in PROPS}
    vals = list(parts.values())
    verdict = round(0.6 * (sum(vals) / len(vals)) + 0.4 * min(vals))
    name, hits = classify(t)
    return parts, verdict, name, hits

def band(v): return "STRONG" if v >= 72 else "WORKABLE" if v >= 55 else "WEAK"

def report(t, parts, verdict, name, hits):
    print(f"\n  {t.strip()}")
    print(f"  {'-' * min(72, max(20, len(t.strip())))}")
    for k, v in parts.items():
        print(f"    {k:<12} {v:3d}  {'#' * (v // 5)}")
    print(f"    {'VERDICT':<12} {verdict:3d}  {band(verdict)}")
    print(f"    formula      {name}" + (f"  ({hits} pattern{'s' if hits != 1 else ''} matched)" if hits else "  (no formula matched - that is usually a summary, not a hook)"))
    low = min(parts, key=parts.get)
    print(f"    weakest      {low} - {FIX[low]}")

FIX = {
 "SPECIFICITY": "swap one adjective for a number, a name or a date",
 "ADDRESS": "say 'you' (మీరు / మీకు) in the first six words",
 "STAKES": "name what it costs them to keep doing it the current way",
 "CURIOSITY": "cut the half of the sentence that answers itself",
 "BREVITY": "9 to 24 words. Read it out loud and stop where you run out of breath",
}

def main():
    T.setup_stdio()
    a = sys.argv[1:]
    as_json = "--json" in a
    a = [x for x in a if x != "--json"]
    if "--hook" in a:
        lines = [a[a.index("--hook") + 1]]
    elif a and os.path.exists(a[0]):
        lines = [l for l in open(a[0], encoding="utf-8-sig").read().splitlines() if l.strip()]
    else:
        print(__doc__); sys.exit(1 if not a else 0)
    out = []
    for t in lines:
        parts, verdict, name, hits = score(t)
        out.append({"hook": t.strip(), "properties": parts, "verdict": verdict,
                    "band": band(verdict), "formula": name, "matched": hits})
    out.sort(key=lambda r: -r["verdict"])
    if as_json:
        print(T.dumps([{k: v for k, v in r.items() if k != "matched"} for r in out])); return
    for r in out:
        report(r["hook"], r["properties"], r["verdict"], r["formula"], r["matched"])
    if len(out) > 1:
        print(f"\n  winner: {out[0]['hook'].strip()}  ({out[0]['verdict']}, {out[0]['band']})\n")

if __name__ == "__main__":
    main()
