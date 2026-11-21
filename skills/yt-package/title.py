#!/usr/bin/env python3
"""title.py - lint a YouTube title and thumbnail pairing before you publish it.

    python3 title.py --title "..." --thumb "AI RAN IT"
    python3 title.py titles.txt            # one per line, ranked
    python3 title.py --title "..." --json

The pairing is the unit, not the title. A title that repeats the thumbnail text wastes half the
click surface, and that is the single most common mistake this checks for.

Length: YouTube truncates around 60 characters on desktop search and around 40 on a mobile home
feed. Both limits are reported because they are different failures - a desktop truncation loses the
tail, a mobile one can lose the subject.

Telugu and mixed titles: the hard limit counts characters as typed; the desktop and mobile cuts
count visible characters (one Telugu akshara = one), and are an ESTIMATE - Telugu glyphs render
wider than Latin ones, so check the real thing on a phone before trusting a near-miss.
"""
import re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_shared"))
try:
    import textutil as T  # noqa: E402
except ImportError:
    sys.exit("title.py needs skills/_shared/textutil.py - install the whole plugin, not one skill folder")

DESKTOP, MOBILE, HARD = 60, 40, 100
VAGUE = {"amazing","incredible","insane","crazy","huge","massive","ultimate","best","powerful",
         "secret","revolutionary","mindblowing","epic","perfect","complete","everything",
         # Telugu (draft - review for the channel's register)
         "అద్భుతం","అద్భుతమైన","షాకింగ్","సంచలనం","సంచలన","భారీ","బెస్ట్","రహస్యం","ఊహించని"}
STOP = {"the","a","an","of","for","to","in","on","and","or","is","are","with","your","you","my","i",
        "this","that","it","how","what","why"} | T.STOP_TE

def words(t): return T.tokens(t)

def _same_word(a, b):
    """Exact, or for Telugu one word plus a suffix (డబ్బు / డబ్బులు) - the language glues
    case and plural endings on, so exact matching misses most real duplicates."""
    if a == b: return True
    if T.script_of(a) != "te" or T.script_of(b) != "te": return False
    short, long_ = sorted((a, b), key=len)
    return T.graphemes(short) >= 2 and long_.startswith(short)

def check(title, thumb=None):
    t = title.strip()
    n = len(t)
    g = T.graphemes(t)
    est = "" if g == n else " (visible characters, estimated)"
    issues, good = [], []
    if n > HARD: issues.append(("length", f"{n} characters - YouTube's hard limit is {HARD}"))
    elif g > DESKTOP: issues.append(("length", f"{g} characters{est} - desktop search cuts near {DESKTOP}"))
    else: good.append(f"{g} characters{est}, inside the {DESKTOP}-character desktop cut")
    if g > MOBILE:
        head = "".join(T.clusters(t)[:MOBILE]).rsplit(" ", 1)[0]
        issues.append(("mobile", f'a mobile feed shows about "{head}..." - check the subject survives'))
    caps = [w for w in t.split() if len(w) > 2 and w.isupper()]
    if len(caps) > 2: issues.append(("shouting", f"{len(caps)} all-caps words - two is the ceiling before it reads as spam"))
    elif caps: good.append(f"{len(caps)} all-caps word for emphasis")
    v = [w for w in words(t) if w in VAGUE]
    if v: issues.append(("vague", f"{', '.join(sorted(set(v)))} - swap for a number, a name or a date"))
    money = T.amounts(t)
    nums = money + [x for x in re.findall(r"\d[\d,.]*%?", t) if not any(x in m for m in money)]
    if nums: good.append(f"carries a concrete figure ({', '.join(nums[:3])})")
    else: issues.append(("no-number", "no number, date or name - the most reliable single fix"))
    if t.endswith("?"): good.append("open question in the title")
    front = [w for w in words(t)[:3] if w not in STOP]
    if not front: issues.append(("front-load", "the first three words are all filler - move the subject forward"))
    if thumb:
        tw, hw = set(words(t)) - STOP, set(words(thumb)) - STOP
        shared = {x for x in tw if any(_same_word(x, y) for y in hw)}
        if shared:
            issues.append(("duplicate", f"thumbnail repeats the title on {', '.join(sorted(shared))} - "
                                        "the thumbnail should say what the title does not"))
        else:
            good.append("thumbnail and title carry different words")
        if len(words(thumb)) > 4:
            issues.append(("thumb-length", f"{len(words(thumb))} words on the thumbnail - three is the ceiling at feed size"))
    score = max(0, min(100, 100 - 14 * len(issues) + 4 * len(good)))
    return {"title": t, "chars": n, "score": score, "issues": issues, "good": good}

def show(r):
    print(f'\n  "{r["title"]}"')
    print(f"  {r['chars']} chars   score {r['score']}/100")
    for k, m in r["issues"]: print(f"    x  {k:<12} {m}")
    for m in r["good"]:      print(f"    ok              {m}")

def main():
    T.setup_stdio()
    a = sys.argv[1:]
    as_json = "--json" in a; a = [x for x in a if x != "--json"]
    thumb = a[a.index("--thumb") + 1] if "--thumb" in a else None
    if "--title" in a:
        rows = [check(a[a.index("--title") + 1], thumb)]
    elif a and os.path.exists(a[0]):
        rows = [check(l, thumb) for l in open(a[0], encoding="utf-8-sig").read().splitlines() if l.strip()]
    else:
        print(__doc__); sys.exit(1)
    rows.sort(key=lambda r: -r["score"])
    if as_json: print(T.dumps(rows)); return
    for r in rows: show(r)
    print()

if __name__ == "__main__":
    main()
