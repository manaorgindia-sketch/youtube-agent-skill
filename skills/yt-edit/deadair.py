#!/usr/bin/env python3
"""deadair.py - an edit decision list from a timestamped transcript.

    python3 deadair.py transcript.srt            # or .vtt, or whisper .json
    python3 deadair.py transcript.srt --floor 0.35 --json
    python3 deadair.py transcript.srt --romanized   # also treat "ante", "sare" as filler

Finds three things and prints the cuts as a list you can act on, newest problem first:
  DEAD    gaps between spoken cues longer than the floor
  FILLER  cues that are only filler ("um", "so yeah", "basically", "అంటే", "సరే")
  REPEAT  a sentence restarted - the second take of the same opening

English, Telugu and mixed transcripts. Filler words are listed in skills/_shared/textutil.py.

WHAT IT DOES NOT DO. It does not cut the file. It prints an EDL, the total it would remove, and the
runtime you would land on, and you apply it in whatever editor you use. Nothing here touches media.
"""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_shared"))
try:
    from textutil import load, parse_ts, tokens, is_filler_only, setup_stdio, dumps  # noqa: F401,E402
except ImportError:
    sys.exit("deadair.py needs skills/_shared/textutil.py - install the whole plugin, not one skill folder")

def is_restart(earlier, later):
    """The earlier cue is an abandoned take of the later one: its opening words (up to five, at
    least three) are exactly the later cue's opening words. Digits are words here, so
    "In 2024 we lost..." followed by "In 2025 we lost..." is two sentences, not a retake."""
    a, b = tokens(earlier), tokens(later)
    k = min(5, len(a))
    return k >= 3 and len(b) >= k and a[:k] == b[:k]

def covered(cuts):
    """Seconds removed, counting overlapping cuts once."""
    total, end = 0.0, None
    for c in sorted(cuts, key=lambda c: c["start"]):
        s = c["start"] if end is None else max(c["start"], end)
        if c["end"] > s: total += c["end"] - s
        end = c["end"] if end is None else max(end, c["end"])
    return total

def edl(cues, floor=0.45, romanized=False):
    filler = [is_filler_only(t, romanized) for _, _, t in cues]
    cuts = []
    for i, (s, e, t) in enumerate(cues):
        if filler[i]:
            cuts.append({"kind": "FILLER", "start": s, "end": e, "why": t.strip()[:48]})
        if i:
            gap = s - cues[i - 1][1]
            if gap > floor:
                keep = floor / 2
                cuts.append({"kind": "DEAD", "start": round(cues[i - 1][1] + keep, 3),
                             "end": round(s - keep, 3), "why": f"{gap:.2f}s gap"})
        # A restart is compared against the last cue that was actually SPEECH. Comparing against
        # the literal previous cue misses every retake with an "um" between the two attempts, which
        # is most of them.
        if t.strip() and not filler[i]:
            j = i - 1
            while j >= 0 and (filler[j] or not cues[j][2].strip()): j -= 1
            if j >= 0 and is_restart(cues[j][2], t):
                opening = " ".join(tokens(cues[j][2])[:5])
                cuts.append({"kind": "REPEAT", "start": cues[j][0], "end": cues[j][1],
                             "why": f'restart of "{opening}"'})
    cuts = [c for c in cuts if c["end"] > c["start"]]
    cuts.sort(key=lambda c: c["start"])
    return cuts, covered(cuts)

def main():
    setup_stdio()
    a = sys.argv[1:]
    as_json = "--json" in a; a = [x for x in a if x != "--json"]
    romanized = "--romanized" in a
    floor = float(a[a.index("--floor") + 1]) if "--floor" in a else 0.45
    a = [x for x in a if not x.startswith("--") and not re.match(r"^[\d.]+$", x)]
    if not a or not os.path.exists(a[0]): print(__doc__); sys.exit(1)
    cues = load(a[0])
    if not cues: print("no cues found - is this an srt, vtt or whisper json?"); sys.exit(1)
    dur = cues[-1][1]
    cuts, removed = edl(cues, floor, romanized)
    if as_json:
        print(dumps({"source": a[0], "duration": dur, "cuts": cuts,
                     "removed": round(removed, 3), "out": round(dur - removed, 3)})); return
    print(f"\n  {a[0]}   {dur:.2f}s in, {len(cues)} cues, dead-air floor {floor}s\n")
    for c in cuts:
        print(f"    {c['kind']:<7} {c['start']:8.2f} -> {c['end']:8.2f}   {c['end']-c['start']:5.2f}s   {c['why']}")
    print(f"\n  {len(cuts)} cuts, {removed:.2f}s removed, {dur - removed:.2f}s out "
          f"({removed / dur * 100:.1f}% shorter)\n")

if __name__ == "__main__":
    main()
