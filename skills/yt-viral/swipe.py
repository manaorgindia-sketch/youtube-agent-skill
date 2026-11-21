#!/usr/bin/env python3
"""swipe.py - rank collected videos by how far each beat its OWN channel, then name the formula.

    python3 swipe.py collected.json
    python3 swipe.py collected.json --min 2.0 --json

Input is a list you collected - one object per video:

    [{"channel":"Some Channel","title":"...","views":412000,"url":"...","duration":613}, ...]

Raw view counts rank channel size, not ideas. A 400k video on a 2M-subscriber channel is a normal
Tuesday; a 400k video on a channel whose median is 30k is the thing worth studying. So every video
is scored as a MULTIPLE OF ITS OWN CHANNEL'S MEDIAN, which needs at least four videos per channel
to mean anything - the tool says so rather than quietly ranking on noise.

The formula comes from skills/yt-script/hooks.json, matched against the TITLE. It is a judgement
about the words on screen, not a claim about why the video worked. Ties go to the formula listed
first in hooks.json, the same rule hookscore.py uses.

"views" may be a number or a string as a page shows it: "412,000", "1.2M", "45K", "12 లక్షలు",
"1.5 crore". Anything unreadable counts as 0 and is reported.
"""
import json, os, re, statistics, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_shared"))
try:
    from textutil import setup_stdio, dumps  # noqa: E402
    from hooks import load_formulas, classify as _classify  # noqa: E402
except ImportError:
    sys.exit("swipe.py needs skills/_shared/ - install the whole plugin, not one skill folder")

FORMULAS = load_formulas()

def classify(title):
    return _classify(title, FORMULAS)[0]

_SCALE = [(r"(?:b|bn|billion)", 1e9), (r"(?:cr|crores?|కోట్లు|కోట్ల|కోటి)", 1e7),
          (r"(?:m|mn|million)", 1e6), (r"(?:l|lakhs?|లక్షలు|లక్షల|లక్ష)", 1e5),
          (r"(?:k|thousand|వేలు|వేల)", 1e3)]

def parse_views(v):
    """412000, "412,000", "1.2M", "12 లక్షలు" -> float. None when it cannot be read."""
    if v is None or v == "": return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().lower().replace(",", "")
    s = re.sub(r"\s*(views?|వీక్షణలు)$", "", s)
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(.*)", s)
    if not m: return None
    num, unit = float(m.group(1)), m.group(2).strip()
    if not unit: return num
    for rx, mult in _SCALE:
        if re.fullmatch(rx, unit): return num * mult
    return None

def main():
    setup_stdio()
    a = sys.argv[1:]
    as_json = "--json" in a; a = [x for x in a if x != "--json"]
    lo = float(a[a.index("--min") + 1]) if "--min" in a else 1.5
    files = [x for x in a if not x.startswith("--") and not re.match(r"^[\d.]+$", x)]
    if not files or not os.path.exists(files[0]): print(__doc__); sys.exit(1)
    with open(files[0], encoding="utf-8-sig") as fh: rows = json.load(fh)
    if isinstance(rows, dict): rows = rows.get("videos", [])
    unreadable = []
    for r in rows:
        n = parse_views(r.get("views"))
        if n is None: unreadable.append(r.get("views")); n = 0.0
        r["_views"] = n
    by = {}
    for r in rows: by.setdefault(r.get("channel", "?"), []).append(r)
    out, thin = [], []
    for ch, vids in by.items():
        views = [v["_views"] for v in vids]
        med = statistics.median(views) if views else 0
        if len(vids) < 4:
            thin.append((ch, len(vids)))
            continue
        for v in vids:
            m = (v["_views"] / med) if med else 0
            out.append({"channel": ch, "title": v.get("title", ""), "views": int(v["_views"]),
                        "median": int(med), "multiple": round(m, 2),
                        "formula": classify(v.get("title", "")), "url": v.get("url", "")})
    out = [r for r in out if r["multiple"] >= lo]
    out.sort(key=lambda r: -r["multiple"])
    if unreadable:
        print(f"  note: {len(unreadable)} view count(s) unreadable, counted as 0: "
              + ", ".join(repr(u) for u in unreadable[:5]), file=sys.stderr)
    if as_json: print(dumps({"outliers": out, "skipped_thin_channels": thin})); return
    print(f"\n  {len(rows)} videos across {len(by)} channels, outliers at {lo}x or better\n")
    for r in out[:25]:
        print(f"    {r['multiple']:5.2f}x  {r['views']:>9,}  vs {r['median']:>9,} median   {r['channel'][:22]:<22} {r['title'][:52]}")
        print(f"            {r['formula']}")
    if not out: print("    nothing cleared the threshold - collect more per channel or lower --min")
    if thin:
        print(f"\n  skipped {len(thin)} channel(s) with under 4 videos collected - a median off one or")
        print( "  two videos is not a median: " + ", ".join(f"{c} ({n})" for c, n in thin[:6]))
    counts = {}
    for r in out: counts[r["formula"]] = counts.get(r["formula"], 0) + 1
    if counts:
        print("\n  formulas among the outliers")
        for f, n in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"    {n:2d}x  {f}")
    print()

if __name__ == "__main__":
    main()
