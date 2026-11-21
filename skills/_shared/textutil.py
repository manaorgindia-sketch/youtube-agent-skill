#!/usr/bin/env python3
"""textutil.py - shared text and transcript helpers for the yt-* tools.

English, Telugu and mixed Telugu/English text, standard library only.

Why this exists. Python's \\w does not match Telugu vowel signs or the virama (they are combining
marks, not letters), so re.findall(r"\\w+", "మీరు") returns ['మ', 'ర'], and every [a-z] pattern in
the tools drops Telugu entirely. Everything that splits, counts or matches words goes through here.

    tokens(text)            words, Telugu marks kept inside the word, Latin lowercased
    word_count(text)        len(tokens(text))
    clusters(text)          visible characters (Telugu aksharalu), for truncation estimates
    graphemes(text)         len(clusters(text))
    script_of(token)        "te" | "latin" | "mixed" | "num" | "other"
    lang_mix(text)          token counts per script and the dominant one
    is_filler_only(text)    the whole cue is filler ("um", "so yeah", "అంటే", "సరే")
    viewer_address(text)    every word that speaks to the viewer ("you", "మీరు", "మీకు", ...)
    amounts(text)           money and Indian magnitudes ("₹5 lakh", "రూ. 10 లక్షలు", "$400")
    load(path), parse_ts(s) srt / vtt / whisper-json transcripts as (start, end, text) cues
    setup_stdio(), dumps()  UTF-8 output and readable (non-escaped) JSON

The Telugu word lists below are a first draft and should be reviewed by a native speaker for the
channel's register before being treated as settled.
"""
import json, re, sys, unicodedata

# --------------------------------------------------------------------------------------- scripts
TE_START, TE_END = 0x0C00, 0x0C7F
VIRAMA = "్"
ZWNJ, ZWJ = "‌", "‍"

def _is_te(ch): return TE_START <= ord(ch) <= TE_END
def _is_te_consonant(ch): return 0x0C15 <= ord(ch) <= 0x0C39 or 0x0C58 <= ord(ch) <= 0x0C5A

# A word is a run of letters/digits, combining marks, the Telugu block and the joiners, with an
# apostrophe allowed between letter runs (don't, you're). Underscore is not a word character here.
_W = r"(?:[^\W_]|[̀-ͯఀ-౿‌‍])"
TOKEN = re.compile(rf"{_W}+(?:['’]{_W}+)*")

def normalize(text):
    """NFC (Telugu has canonical compositions, e.g. ై), straight apostrophes."""
    return unicodedata.normalize("NFC", text or "").replace("’", "'").replace("‘", "'")

def tokens(text):
    """Words in order. Latin is lowercased; Telugu has no case and is left as written."""
    return [t.lower() for t in TOKEN.findall(normalize(text))]

def word_count(text):
    return len(tokens(text))

def script_of(token):
    te = any(_is_te(c) and not c.isdigit() for c in token)
    la = any(c.isascii() and c.isalpha() for c in token)
    if te and la: return "mixed"
    if te: return "te"
    if la: return "latin"
    if token and all(c.isdigit() or c in ".,'" for c in token): return "num"
    return "other"

def lang_mix(text):
    """{"te": n, "latin": n, "mixed": n, "num": n, "other": n, "dominant": "te"|"latin"|None}"""
    out = {"te": 0, "latin": 0, "mixed": 0, "num": 0, "other": 0}
    for t in tokens(text): out[script_of(t)] += 1
    words = {k: out[k] for k in ("te", "latin")}
    out["dominant"] = max(words, key=words.get) if any(words.values()) else None
    return out

def clusters(text):
    """User-perceived characters. A Telugu akshara (consonant [+ virama + consonant ...] + vowel
    sign + anusvara/visarga) is one cluster; marks and joiners never start a new one. An estimate
    for truncation, not a full UAX #29 implementation."""
    out, prev = [], ""
    for ch in normalize(text):
        joins = (unicodedata.category(ch).startswith("M") or ch in (ZWJ, ZWNJ)
                 or (prev == VIRAMA and _is_te_consonant(ch)))   # క్క is one akshara
        if joins and out: out[-1] += ch
        else: out.append(ch)
        prev = ch
    return out

def graphemes(text):
    return len(clusters(text))

# ----------------------------------------------------------------------------------- stopwords
STOP_TE = set("""
ఈ ఆ ఒక ఒక్క మరియు కూడా అని ఇది అది ఇవి అవి ఉంది ఉన్నాయి ఉన్నారు ఉంటుంది ఉండి కి కు ని ను తో
లో మీద నుంచి నుండి వరకు గురించి కోసం చాలా ఇంకా అయితే కానీ లేదా ఎందుకంటే అంటే మనం నేను మేము
మా మన వారు వాళ్ళు అతను ఆమె ఏ ఎలా ఏమి ఏం ఏంటి ఎవరు ఎక్కడ ఎప్పుడు ఎందుకు అవును కాదు లేదు
అవుతుంది చేసి చేయడం ఇప్పుడు అప్పుడు ఇక్కడ అక్కడ మీ మీరు మీకు ఇక మరి అలా ఇలా
""".split())

# ------------------------------------------------------------------------------------- fillers
# English: the same set deadair.py has always used. Telugu: DRAFT - review with the channel.
_FILLER_EN_WORD = re.compile(r"^(um+|uh+|er+|ah+|so|okay|ok|right|yeah|like|anyway|basically|actually)$")
FILLER_EN_PHRASES = [("you", "know"), ("i", "mean"), ("let", "me", "see"), ("hold", "on")]
_FILLER_TE_WORD = re.compile(r"^(అంటే|అది|ఆ+ఁ?|ఊ+|(హా)+|సరే|మరి|ఇక|అలా|కదా|అసలు|ఏంటంటే|చూడండి|ఓకే)$")
FILLER_TE_ROMAN = {"ante", "sare", "mari", "ika", "ala", "kada", "kadha", "asalu", "entante",
                   "chudandi", "aa", "aaa", "oo", "haa", "okay"}

def is_filler_only(text, romanized=False):
    """True when every word in the cue is filler. A cue with one real word is never filler -
    that is what keeps a meaningful "అది" or "right" from being cut."""
    ts = tokens(text)
    if not ts: return False
    i = 0
    while i < len(ts):
        for ph in FILLER_EN_PHRASES:
            if tuple(ts[i:i + len(ph)]) == ph:
                i += len(ph); break
        else:
            t = ts[i]
            if not (_FILLER_EN_WORD.match(t) or _FILLER_TE_WORD.match(t)
                    or (romanized and t in FILLER_TE_ROMAN)):
                return False
            i += 1
    return True

# ----------------------------------------------------------------------------- viewer address
# Exact forms, never a prefix match: "మీద" (on top of) and "మీదకు" start with "మీ" and are not
# the viewer. Telugu list is a DRAFT - review with the channel.
VIEWER_EN = {"you", "your", "you're", "youre", "yourself", "you've", "you'll", "you'd"}
VIEWER_TE = {"మీరు", "మీ", "మీకు", "మిమ్మల్ని", "మీది", "మీరే", "మీకే", "మీలో", "మీతో", "మీకోసం",
             "మీరందరూ", "మీరూ"}

def viewer_address(text):
    """[(word_index, word), ...] for every word addressed to the viewer."""
    return [(i, t) for i, t in enumerate(tokens(text)) if t in VIEWER_EN or t in VIEWER_TE]

# ------------------------------------------------------------------------------------- amounts
# No \b around Telugu: \b is defined by \w, which stops at vowel signs. Use explicit edges.
_EDGE_L = r"(?<![\wఀ-౿])"
_EDGE_R = r"(?![\wఀ-౿])"
_NUM = r"\d[\d,]*(?:\.\d+)?"                      # \d also matches Telugu digits ౦-౯
_MAG = (r"(?:lakhs?|crores?|thousand|million|billion|"
        r"లక్షలు|లక్షల|లక్ష|కోట్లు|కోట్ల|కోటి|వేలు|వేల|"
        r"cr|k|m|l|bn)")
_CUR = r"(?:₹|\$|rs\.?|inr|usd|రూ\.?)"
_UNIT = r"(?:రూపాయలు|రూపాయల|rupees?|dollars?|bucks)"
_BIG = r"(?:lakhs?|crores?|million|billion|లక్షలు|లక్షల|లక్ష|కోట్లు|కోట్ల|కోటి)"   # no digit needed
AMOUNT = re.compile(
    rf"{_EDGE_L}{_CUR}\s?{_NUM}(?:\s?{_MAG})?{_EDGE_R}"      # ₹5 lakh, Rs. 500, రూ. 10 లక్షలు, $4k
    rf"|{_EDGE_L}{_NUM}\s?{_MAG}(?:\s?{_UNIT})?{_EDGE_R}"    # 10 లక్షలు, 2 crore rupees, 40k
    rf"|{_EDGE_L}{_NUM}\s?{_UNIT}{_EDGE_R}"                  # 500 rupees, 300 రూపాయలు
    rf"|{_EDGE_L}{_BIG}(?:\s?{_UNIT})?{_EDGE_R}",            # కోటి రూపాయలు, లక్షల మంది, a million
    re.I)

def amounts(text):
    """Money and Indian magnitudes, as written. Plain numbers and percentages are not amounts."""
    return [m.group(0).strip() for m in AMOUNT.finditer(normalize(text))]

def has_digit_free_amount(text):
    """An amount said in words only ("కోటి రూపాయలు", "a million") - no digit for a number check."""
    return any(not any(c.isdigit() for c in a) for a in amounts(text))

# ---------------------------------------------------------------------------------- transcripts
def parse_ts(s):
    s = s.strip().replace(",", ".")
    p = s.split(":")
    return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2]) if len(p) == 3 else int(p[0]) * 60 + float(p[1])

def load(path):
    """srt, vtt or whisper json -> [(start, end, text), ...]. Cues with no text are dropped."""
    with open(path, encoding="utf-8-sig", errors="replace") as fh: raw = fh.read()
    if path.endswith(".json"):
        d = json.loads(raw)
        segs = d.get("segments", []) if isinstance(d, dict) else d
        return [(float(s["start"]), float(s["end"]), (s.get("text") or "").strip()) for s in segs]
    cues, cur = [], None
    for line in raw.splitlines():
        m = re.match(r"\s*(\d[\d:.,]+)\s*-->\s*(\d[\d:.,]+)", line)
        if m:
            cur = [parse_ts(m.group(1)), parse_ts(m.group(2)), []]
            cues.append(cur)
        elif cur is not None and line.strip() and not line.strip().isdigit():
            cur[2].append(line.strip())
    return [(a, b, " ".join(t)) for a, b, t in cues if t]

# --------------------------------------------------------------------------------------- output
def setup_stdio():
    """Print Telugu on any console. Python < 3.15 on Windows defaults to cp1252 and crashes."""
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError): pass

def dumps(obj, indent=1):
    """JSON with Telugu left readable instead of \\u0c2e escapes."""
    return json.dumps(obj, indent=indent, ensure_ascii=False)
