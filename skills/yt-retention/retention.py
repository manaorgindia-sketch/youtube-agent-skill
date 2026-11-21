#!/usr/bin/env python3
"""retention.py - read a YouTube Studio audience-retention export and find the leaks.

    python3 retention.py retention.csv
    python3 retention.py retention.csv --duration 600                # seconds, for a percent axis
    python3 retention.py retention.csv --transcript transcript.srt   # names what was said at each drop
    python3 retention.py retention.csv --axis seconds                # override axis detection
    python3 retention.py retention.csv --json

Get the file from Studio: Analytics -> a video -> Engagement -> the audience-retention chart ->
the download icon -> "Audience retention". Two columns, a position (percent or seconds) and a
percentage still watching. Flags may come in any order.

It reports three things, because they are three different problems with three different fixes:
  HOOK LEAK    what you lost in the first 30 seconds
  CLIFFS       single steep drops - a specific moment people left at
  SLIDE        the steady bleed rate across the flat middle

With --transcript it prints what you were saying at each cliff, which is the only version of this
report you can act on without scrubbing the video yourself. A percent axis needs --duration for
that, so the tool can turn 40% into a second.

AXIS. The position column is read as seconds or percent from its header ("%", "percent" vs
"second", "time"). With no header it guesses: past 100 is seconds; a series that ends well short
of 100 is seconds (a Short); one that reaches ~100 is percent. The guess is printed. --axis wins.
"""
import argparse, csv, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_shared"))
try:
    from textutil import load as load_cues, setup_stdio, dumps  # noqa: E402
except ImportError:
    sys.exit("retention.py needs skills/_shared/textutil.py - install the whole plugin, not one skill folder")

def load_csv(path):
    """(rows, header) - rows are (position, retention); header is the first row with no numbers."""
    rows, header = [], None
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.reader(fh):
            nums = []
            for c in r:
                c = c.strip().replace("%", "").replace(",", "")
                try: nums.append(float(c))
                except ValueError: nums.append(None)
            vals = [n for n in nums if n is not None]
            if len(vals) >= 2: rows.append((vals[0], vals[1]))
            elif not rows and header is None and any(c.strip() for c in r): header = r
    return rows, header

def detect_axis(xs, header=None, duration=None):
    """("percent" | "seconds", how it was decided)."""
    if header:
        h = header[0].lower()
        if "%" in h or "percent" in h: return "percent", "header"
        if any(k in h for k in ("second", "sec)", "time")): return "seconds", "header"
    top = max(xs)
    if top > 100.5: return "seconds", "values past 100"
    if duration and duration < 95:
        return ("seconds", "values fit the duration") if top <= duration * 1.05 + 1 else ("percent", "values past the duration")
    if top >= 95: return "percent", "values reach ~100"
    return "seconds", "values end short of 100"

def analyse(rows, axis, dur=None, cues=None):
    xs = [r[0] for r in rows]; ys = [r[1] for r in rows]
    pct_axis = axis == "percent"
    def at(x): return (x / 100.0 * dur) if (pct_axis and dur) else x
    start = ys[0] or 100.0
    # HOOK: the first 30 seconds, or the first 10% when the axis is a percentage and we have no duration
    cutoff = 30.0 if not pct_axis else (30.0 / dur * 100 if dur else 10.0)
    hook_end = min((y for x, y in rows if x <= cutoff), default=start)
    hook_leak = start - hook_end
    drops = []
    for i in range(1, len(rows)):
        d = ys[i - 1] - ys[i]
        span = xs[i] - xs[i - 1] or 1
        drops.append((d / span, xs[i - 1], xs[i], d))
    drops.sort(reverse=True)
    cliffs = [{"from": round(a1, 2), "to": round(b1, 2), "lost": round(d, 2),
               "at_seconds": round(at(a1), 1) if (not pct_axis or dur) else None}
              for _, a1, b1, d in drops[:5] if d > 0.8]
    mid = [rate for rate, x0, _, _ in drops if x0 > cutoff]
    slide = sum(mid) / len(mid) if mid else 0
    said = {}
    for c in cliffs if cues else []:
        if c["at_seconds"] is None: continue
        t = c["at_seconds"]
        near = [q[2] for q in cues if q[0] <= t + 4 and q[1] >= t - 4]
        said[str(c["from"])] = " ".join(near)[:140]
    return {"points": len(rows), "axis": axis, "start": start, "hook_leak": round(hook_leak, 2),
            "end": ys[-1], "cliffs": cliffs, "slide_per_unit": round(slide, 3), "said": said}

def main():
    setup_stdio()
    p = argparse.ArgumentParser()
    p.add_argument("csv", nargs="?")
    p.add_argument("--transcript")
    p.add_argument("--duration", type=float)
    p.add_argument("--axis", choices=("auto", "seconds", "percent"), default="auto")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    if not args.csv or not os.path.exists(args.csv): print(__doc__); sys.exit(1)
    rows, header = load_csv(args.csv)
    if len(rows) < 8: print("could not read at least 8 data points from that csv"); sys.exit(1)
    xs = [r[0] for r in rows]
    if args.axis == "auto": axis, why = detect_axis(xs, header, args.duration)
    else: axis, why = args.axis, "--axis"
    cues = load_cues(args.transcript) if args.transcript and os.path.exists(args.transcript) else None
    if args.transcript and cues is None:
        print(f"  note: transcript {args.transcript} not found - skipping what-was-said", file=sys.stderr)
    if cues and axis == "percent" and not args.duration:
        print("  note: percent axis with no --duration - cannot place cliffs in the transcript", file=sys.stderr)
    out = analyse(rows, axis, args.duration, cues)
    out["axis_from"] = why
    if args.json: print(dumps(out)); return
    hook_leak, cliffs, said, slide = out["hook_leak"], out["cliffs"], out["said"], out["slide_per_unit"]
    print(f"\n  {args.csv}   {len(rows)} points   {rows[0][1]:.1f}% -> {rows[-1][1]:.1f}%   axis {axis} ({why})\n")
    verdict = "healthy" if hook_leak < 25 else "leaking" if hook_leak < 40 else "severe"
    print(f"  HOOK LEAK   {hook_leak:.1f}% lost in the opening   [{verdict}]")
    print(f"              under 25 is healthy for this length. Fix the first line before anything else.\n")
    print("  CLIFFS      the moments people actually left")
    for c in cliffs:
        where = f"{c['at_seconds']:.0f}s" if c["at_seconds"] is not None else f"{c['from']}"
        print(f"    -{c['lost']:5.1f}%  at {where:>8}" + (f"   \"{said.get(str(c['from']),'')}\"" if said else ""))
    if not cliffs: print("    none steeper than 0.8% - the loss is all slide, not moments")
    print(f"\n  SLIDE       {slide:.3f}% per unit across the middle")
    print( "              a flat slide is pacing, not content. Cut the middle, do not rewrite it.\n")

if __name__ == "__main__":
    main()
