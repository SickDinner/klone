"""Descriptive metrics for explicitly supplied creative lyrics.

No model calls, interpretation of authors, external retrieval or persistent writes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unicodedata

MAX_BYTES = 256_000
MAX_LINES = 10_000
_SECTION = re.compile(r"^\[([^\[\]]{1,80})\]$")
_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


def moving_average_ttr(words: list[str], window: int) -> float | None:
    """Mean lexical diversity of fixed-size overlapping token windows."""
    if type(window) is not int or window <= 0:
        raise ValueError("Window must be a positive integer")
    if len(words) < window:
        return None
    counts = Counter(words[:window])
    total_unique = len(counts)
    for i in range(window, len(words)):
        old, new = words[i - window], words[i]
        counts[old] -= 1
        if counts[old] == 0:
            del counts[old]
        counts[new] += 1
        total_unique += len(counts)
    return round(total_unique / (window * (len(words) - window + 1)), 8)


def analyze_lyrics(text: str) -> dict:
    if not isinstance(text, str):
        raise ValueError("Expected text")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Lyrics exceed byte limit")
    text = unicodedata.normalize("NFC", text)
    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError("Lyrics exceed line limit")
    sections = []
    label = "unlabeled"
    body = []
    words = []
    normalized_lines = []
    line_word_counts = []
    adjacent_initial_matches = 0
    adjacent_word_pairs = 0
    endings = []
    suffix_patterns = {
        str(distance): {"eligible_pairs": 0, "identical_end_words": 0,
                        "suffix_2": 0, "suffix_3": 0, "suffix_4": 0}
        for distance in (1, 2)
    }

    def flush():
        if body or label != "unlabeled":
            sections.append({
                "label": label,
                "line_count": len(body),
                "word_count": sum(len(_WORD.findall(line)) for line in body),
            })

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        marker = _SECTION.fullmatch(line)
        if marker:
            flush()
            label = marker[1].strip()
            body = []
            endings = []
            continue
        body.append(line)
        tokens = [word.casefold() for word in _WORD.findall(line)]
        words.extend(tokens)
        ending = tokens[-1] if tokens and tokens[-1].isalpha() else None
        for distance in (1, 2):
            if ending is None or len(endings) < distance:
                continue
            previous = endings[-distance]
            if previous is None:
                continue
            stats = suffix_patterns[str(distance)]
            stats["eligible_pairs"] += 1
            if previous == ending:
                stats["identical_end_words"] += 1
                continue
            for size in (2, 3, 4):
                if min(len(previous), len(ending)) >= size and previous[-size:] == ending[-size:]:
                    stats[f"suffix_{size}"] += 1
        endings.append(ending)
        if len(endings) > 2:
            endings.pop(0)
        line_word_counts.append(len(tokens))
        for first, second in zip(tokens, tokens[1:]):
            if first[0].isalpha() and second[0].isalpha():
                adjacent_word_pairs += 1
                adjacent_initial_matches += int(first[0] == second[0])
        normalized_lines.append(" ".join(line.casefold().split()))
    flush()
    frequencies = Counter(normalized_lines)
    n = len(normalized_lines)
    return {
        "schema": "klone.lyrics_metrics.v1",
        "normalized_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "line_count": n,
        "word_count": len(words),
        "unique_word_count": len(set(words)),
        "type_token_ratio": round(len(set(words)) / len(words), 8) if words else None,
        "repeated_line_occurrences": sum(v - 1 for v in frequencies.values()),
        "sections": sections,
        "orthographic_end_patterns": suffix_patterns,
        "mattr": {str(window): moving_average_ttr(words, window)
                  for window in (10, 25, 50)},
        "line_word_counts": line_word_counts,
        "adjacent_initial_matches": adjacent_initial_matches,
        "adjacent_word_pairs": adjacent_word_pairs,
        "limitations": [
            "Descriptive text counts, not artistic quality or author profiling.",
            "Type-token ratio depends on text length; no language-specific lemmatization.",
            "Repeated lines use case and whitespace normalization, not semantic equivalence.",
            "MATTR compares fixed token windows; null means insufficient tokens.",
            "Initial-letter matches are orthographic, not validated phonetic alliteration.",
            "End-pattern counts compare written suffixes within sections at distances 1 and 2; nested counts exclude identical end words and are not phonetic rhyme.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.path.open("rb") as source:
            raw = source.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Lyrics exceed byte limit")
        report = analyze_lyrics(raw.decode("utf-8"))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
