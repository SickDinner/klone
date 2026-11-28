"""Descriptive orthographic study of explicitly supplied Finnish creative verse."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import unicodedata

from .lyrics_metrics import MAX_BYTES, MAX_LINES
from .written_verse_rhythm import written_verse_rhythm

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_SECTION = re.compile(r"^\[[^\[\]]{1,80}\]$")
_FRONT = frozenset("yäö")
_BACK = frozenset("aou")
_NEUTRAL = frozenset("ei")
DEMO = "Kuu kulkee kultarannan\nTuuli tuudittaa tunturia\n\nYö yllä järven jäällä\nYö yllä metsän säällä"


def _harmony(word):
    letters = set(word)
    front, back = bool(letters & _FRONT), bool(letters & _BACK)
    if front and back:
        return "mixed_front_back"
    if front:
        return "front"
    if back:
        return "back"
    return "neutral_only" if letters & _NEUTRAL else "no_recognized_vowel"


def poetry_study(text: str) -> dict:
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Expected bounded UTF-8 verse")
    lines = unicodedata.normalize("NFC", text).splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError("Too many lines")
    harmony = Counter({key: 0 for key in (
        "front", "back", "mixed_front_back", "neutral_only", "no_recognized_vowel")})
    stanzas = []
    rows = []
    adjacent = []
    previous = None
    stanza = None
    for raw in lines:
        line = raw.strip()
        if not line or _SECTION.fullmatch(line):
            previous = None
            stanza = None
            continue
        words = _WORD.findall(line.casefold())
        if not words:
            previous = None
            continue
        if stanza is None:
            stanza = {"stanza_index": len(stanzas) + 1, "line_count": 0}
            stanzas.append(stanza)
        stanza["line_count"] += 1
        harmony.update(_harmony(word) for word in words)
        pairs = list(zip(words, words[1:]))
        initials = sum(a != b and a[0] == b[0] for a, b in pairs)
        rhythm = written_verse_rhythm(line)["written_vowel_groups_per_line"][0]
        rows.append({
            "line_index": len(rows) + 1,
            "stanza_index": stanza["stanza_index"],
            "word_count": len(words),
            "written_vowel_groups": rhythm,
            "adjacent_word_pairs": len(pairs),
            "distinct_word_initial_matches": initials,
        })
        if previous is not None:
            a, b = set(previous), set(words)
            prefix = 0
            for x, y in zip(previous, words):
                if x != y:
                    break
                prefix += 1
            adjacent.append({
                "first_line_index": len(rows) - 1,
                "second_line_index": len(rows),
                "shared_word_types": len(a & b),
                "word_type_jaccard": round(len(a & b) / len(a | b), 8),
                "shared_prefix_words": prefix,
            })
        previous = words
    return {
        "schema": "klone.nordic_poetry.v1",
        "line_count": len(rows),
        "word_count": sum(row["word_count"] for row in rows),
        "stanzas": stanzas,
        "vowel_harmony_word_counts": dict(harmony),
        "lines": rows,
        "within_stanza_adjacent_lines": adjacent,
        "limitations": [
            "Written Finnish letter patterns, not phonetic alliteration or syllabification.",
            "Vowel harmony categories describe letters, not grammatical correctness; compounds and loans can be mixed.",
            "Neutral letters are e and i; other unrecognized vowels are not classified as Finnish harmony vowels.",
            "Adjacent line overlap uses exact casefolded word forms, not semantic parallelism or lemmatization.",
            "Blank lines and bracketed section markers delimit stanzas.",
            "No Kalevala meter verdict, aesthetic score or author inference; no original words included in report.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true")
    source.add_argument("--lyrics", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.demo:
            text = DEMO
        else:
            with args.lyrics.open("rb") as handle:
                raw = handle.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("Verse exceeds byte limit")
            text = raw.decode("utf-8")
        report = poetry_study(text)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
