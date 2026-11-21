#!/usr/bin/env python3
"""hooks.py - the one loader and classifier for skills/yt-script/hooks.json.

hookscore.py (scores spoken hooks) and swipe.py (classifies titles) used to each carry their own
copy of this, with different tie-breaks: hookscore kept the first formula to reach the top count,
swipe kept the alphabetically last name. The same line could get two different formulas. This is
the single rule now: most patterns matched wins, ties go to the formula listed first in the file.

A formula may carry an optional "match_te" list of Telugu patterns next to "match"; both count.
"""
import json, os, re

HOOKS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "yt-script", "hooks.json")

def load_formulas(path=HOOKS_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["hooks"]

def hits(formula, text):
    return sum(1 for p in formula.get("match", []) + formula.get("match_te", [])
               if re.search(p, text, re.I))

def classify(text, formulas):
    """(formula name, patterns matched). ("Unclassified", 0) when nothing matches."""
    best, top = None, 0
    for f in formulas:
        n = hits(f, text)
        if n > top: best, top = f, n
    return (best["name"] if best else "Unclassified"), top
