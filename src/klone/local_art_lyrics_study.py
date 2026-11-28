"""Bounded local UTF-8 lyric structure study, not phonetic or semantic analysis."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import stat
import unicodedata

MAX_BYTES = 256 * 1024
MAX_LINES = 4096
MAX_LINE_CHARS = 4096
WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
SECTION = re.compile(
    r"\[(intro|verse|pre-chorus|chorus|post-chorus|bridge|outro|hook|instrumental)"
    r"(?:[ \t]+[0-9]{1,3})?\]", re.IGNORECASE)
VOWELS = frozenset("aeiouyäöå")


def _words(line):
    return WORD.findall(unicodedata.normalize("NFC", line.casefold()))


def _vowel_groups(word):
    return sum(c in VOWELS and (i == 0 or word[i-1] not in VOWELS)
               for i, c in enumerate(word))


def _fraction(n, d):
    return n / d if d else None


def analyze_lyrics(path):
    path = Path(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("expected regular local UTF-8 text file")
    with path.open("rb") as f:
        data = f.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("text byte limit exceeded")
    lines = data.decode("utf-8-sig", errors="strict").splitlines()
    if len(lines) > MAX_LINES or any(len(line) > MAX_LINE_CHARS for line in lines):
        raise ValueError("text line limit exceeded")

    sections = []
    stanzas = []
    active = []
    section = None
    rows = []
    normalized_lines = []
    token_counts = Counter()
    initials = eligible_initials = 0

    def flush():
        nonlocal active
        if active:
            stanzas.append(active)
            active = []

    for number, line in enumerate(lines, 1):
        label = SECTION.fullmatch(line.strip())
        if label:
            flush()
            section = {"kind": label.group(1).lower(), "header_line": number,
                       "lyric_line_count": 0}
            sections.append(section)
            continue
        words = _words(line)
        if not words:
            flush()
            continue
        if section is not None:
            section["lyric_line_count"] += 1
        token_counts.update(words)
        normalized_lines.append(tuple(words))
        matches = sum(a[0] == b[0] for a, b in zip(words, words[1:]))
        initials += matches
        eligible_initials += len(words) - 1
        rows.append({"source_line": number,
                     "word_count": len(words),
                     "written_vowel_group_count": sum(_vowel_groups(w) for w in words),
                     "adjacent_initial_matches": matches,
                     "adjacent_word_pairs": len(words)-1})
        active.append((number, words[-1]))
    flush()

    rhyme = []
    eligible_end_pairs = 0
    identical_ends = 0
    for stanza in stanzas:
        for (a_line, a), (b_line, b) in zip(stanza, stanza[1:]):
            if min(len(a), len(b)) < 3:
                continue
            eligible_end_pairs += 1
            if a == b:
                identical_ends += 1
                continue
            if a[-3:] == b[-3:]:
                rhyme.append({"source_lines":[a_line,b_line], "shared_suffix_chars":3})

    line_counts = Counter(normalized_lines)
    word_count = sum(token_counts.values())
    repeat_occurrences = sum(n-1 for n in line_counts.values())
    return {
        "schema": "klone.local_art_lyrics_study.v1",
        "source": {"sha256": hashlib.sha256(data).hexdigest(),
                   "encoding":"UTF-8", "byte_count":len(data)},
        "structure": {"lyric_line_count":len(rows), "stanza_count":len(stanzas),
                      "sections":sections, "line_metrics":rows},
        "lexical_metrics": {
            "word_count":word_count, "distinct_word_forms":len(token_counts),
            "type_token_ratio":_fraction(len(token_counts),word_count),
            "repeated_normalized_line_occurrences":repeat_occurrences,
            "repeated_normalized_line_fraction":_fraction(repeat_occurrences,len(rows)),
            "adjacent_initial_matches":initials,
            "adjacent_word_pairs":eligible_initials,
            "adjacent_initial_match_fraction":_fraction(initials,eligible_initials),
        },
        "line_end_metrics": {
            "eligible_adjacent_end_pairs":eligible_end_pairs,
            "identical_end_word_pairs":identical_ends,
            "distinct_end_word_suffix_matches":len(rhyme),
            "distinct_end_word_suffix_match_fraction":_fraction(len(rhyme),eligible_end_pairs),
            "matching_line_pairs":rhyme,
        },
        "limitations":[
            "Explicit local UTF-8 text; bounded bytes, line count and line length.",
            "NFC and casefold; contiguous Unicode letters approximate written word forms, not lemmas.",
            "Recognized bracketed song headings are structural markers, not lyrics.",
            "Blank or non-word lines and recognized headers break stanzas.",
            "Written Finnish vowel groups are not verified syllable counts.",
            "Adjacent same-initial words approximate written alliteration, not pronunciation.",
            "Adjacent stanza-internal line endings of at least three characters: identical words counted separately; three-character suffix agreement is not phonetic rhyme.",
            "Repeated lines compare normalized word sequences; fraction counts occurrences beyond the first.",
            "No quoted lyric text, filename, language identification, emotion inference, quality score or personal profiling.",
            "No network, external model, persistent memory or production integration.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lyrics", type=Path)
    args = parser.parse_args(argv)
    try:
        result = analyze_lyrics(args.lyrics)
    except (OSError, ValueError) as exc:
        parser.exit(2, "Lyric analysis failed: " + str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
