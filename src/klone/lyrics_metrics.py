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
            continue
        body.append(line)
        words.extend(word.casefold() for word in _WORD.findall(line))
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
        "limitations": [
            "Descriptive text counts, not artistic quality or author profiling.",
            "Type-token ratio depends on text length; no language-specific lemmatization.",
            "Repeated lines use case and whitespace normalization, not semantic equivalence.",
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
