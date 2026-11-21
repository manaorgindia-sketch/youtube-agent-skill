# youtube-agent-skill - AZ VAARTHA fork

Eleven Claude skills for running a YouTube channel, extended here for Telugu and mixed
Telugu/English production. Fork of `Jakeschincariol/youtube-agent-skill`.

## Rules

1. Keep all 11 skills. Never delete, rename or merge a `skills/yt-*` folder.
2. Never touch the `upstream` remote. Work goes to `origin` (the fork) on a feature branch.
3. No commit or push without the user's explicit approval for that commit or push.
4. Read the existing code before editing it.
5. Explain each change before applying it.

## Layout

```
skills/yt-*/SKILL.md     the 11 skills (instructions Claude follows)
skills/yt-*/*.py         six tools: hookscore, title, deadair, chapters, retention, swipe
skills/yt-script/hooks.json   the 21 hook formulas - stays here; SKILL.md files link to it
skills/_shared/          code the tools share - NOT a skill (no SKILL.md, must never get one)
  textutil.py            Telugu-aware tokens, counts, fillers, viewer address, amounts, transcripts
  hooks.py               the one hooks.json loader and formula classifier
tests/                   unittest suite; fixtures in tests/fixtures/{en,te,mixed}/
```

## Conventions

- **Standard library only.** No pip dependencies. Python 3.10 is the floor (CI checks the grammar).
- **Text goes through `textutil`.** Never split or match words with `\w`, `[a-z]` or `\b` on
  Telugu: `\w` does not match vowel signs or the virama, so `మీరు` splits into `మ`, `ర`. Use
  `tokens()`, `word_count()`, `graphemes()`, and the explicit edges used in `AMOUNT`.
- **Tools import `_shared` by path** (`sys.path.insert(0, .../_shared)`) and exit with a clear
  message if it is missing. Don't add new cross-skill imports (`../yt-edit` and similar).
- **Encoding:** open every file with `encoding="utf-8"` (or `utf-8-sig` for user input), call
  `setup_stdio()` in `main()`, and write JSON with `dumps()` so Telugu stays readable.
- **Telugu word lists are drafts** (fillers, viewer address, stakes, curiosity, vague words). They
  need review by a native speaker for the channel's register. Viewer address is exact-match only:
  `మీద` (on top of) starts with `మీ` and is not the viewer.
- **hooks.json:** keep all 21 formulas. Telugu patterns go in an optional `match_te` list next to
  `match`. Ties go to the formula listed first - order in the file matters.
- **English behaviour is pinned.** `tests/fixtures/en/expected/*.json` is the reviewed English
  output. A change that moves it must be intended and the diff explained.

## Tests

```bash
python -m unittest discover -s tests                         # all tests, ~5s
UPDATE_GOLDEN=1 python -m unittest discover -s tests         # re-record English baselines, then review the diff
```

Every bug fix gets a test in `tests/test_regressions.py` naming the bug. CI
(`.github/workflows/tests.yml`) runs the suite on ubuntu and windows, Python 3.10 / 3.13 / latest.

## Open items

- Telugu hook brevity still uses the English 9-24 word band; recalibrate on real AZ VAARTHA hooks.
- No `match_te` patterns yet, so Telugu hooks classify as Unclassified unless English patterns hit.
- Title truncation for Telugu is a visible-character estimate; Telugu glyphs render wider.
