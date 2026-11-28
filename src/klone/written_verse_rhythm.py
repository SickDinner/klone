"""Written Finnish verse rhythm proxies, not a phonetic syllabifier."""
from __future__ import annotations

from collections import Counter
import re
import unicodedata

from .lyrics_metrics import MAX_BYTES, MAX_LINES

_VOWEL_GROUP = re.compile(r"[aeiouyäöå]+")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_SECTION = re.compile(r"^\[[^\[\]]{1,80}\]$")


def written_verse_rhythm(text: str) -> dict:
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Expected bounded UTF-8 text")
    lines = unicodedata.normalize("NFC", text).splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError("Too many lines")
    groups = []
    for line in lines:
        line = line.strip()
        if not line or _SECTION.fullmatch(line):
            continue
        words = _WORD.findall(line.casefold())
        groups.append(sum(len(_VOWEL_GROUP.findall(word)) for word in words))
    histogram = Counter(groups)
    return {
        "schema": "klone.written_verse_rhythm.v1",
        "line_count": len(groups),
        "written_vowel_groups_per_line": groups,
        "vowel_group_histogram": {str(k): v for k, v in sorted(histogram.items())},
        "mean_vowel_groups": round(sum(groups) / len(groups), 8) if groups else None,
        "equal_adjacent_counts": sum(a == b for a, b in zip(groups, groups[1:])),
        "limitations": [
            "Counts contiguous written Finnish vowel groups per word.",
            "Not syllabification, stress, phonetic scansion or a meter classification.",
            "Hiatus, loanwords, abbreviations and pronunciation may differ.",
            "Adjacent counts compare nonblank non-header lines, including across sections.",
        ],
    }
