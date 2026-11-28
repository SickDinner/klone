"""Bounded, opt-in local artwork research collection.

Builds a transient JSON catalog from explicitly selected files. Does not scan
directories, copy original media, manage identities or write a database.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import wave

from PIL import Image
from .local_art_image_study import analyze_image
from .local_art_audio_study import analyze_audio
from .local_art_lyrics_study import analyze_lyrics

MAX_ITEMS = 12


def _digest(value):
    data = json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def creative_archive(items):
    """Analyze an ordered list of (media_kind, local_path) selections."""
    if not 1 <= len(items) <= MAX_ITEMS:
        raise ValueError("select between 1 and 12 artwork files")
    analyzers = {"image": analyze_image, "audio": analyze_audio,
                 "lyrics": analyze_lyrics}
    if any(kind not in analyzers for kind, _ in items):
        raise ValueError("unsupported artwork kind")

    records = []
    selections = []
    by_key = {}
    for index, (kind, path) in enumerate(items, 1):
        report = analyzers[kind](Path(path))
        digest = report["source"]["sha256"]
        key = (kind, digest)
        report_digest = _digest(report)
        if key in by_key:
            record = by_key[key]
            if record["report_sha256"] != report_digest:
                raise ValueError("inconsistent report for repeated source")
            duplicate = True
        else:
            record = {
                "record_id": kind + ":" + digest,
                "media_kind": kind,
                "source_sha256": digest,
                "report_sha256": report_digest,
                "report_schema": report["schema"],
                "report": report,
            }
            records.append(record)
            by_key[key] = record
            duplicate = False
        selections.append({"selection_index": index,
                           "record_id": record["record_id"],
                           "duplicate_within_collection": duplicate})

    return {
        "schema": "klone.local_creative_archive.v1",
        "records": records,
        "selections": selections,
        "inventory": {
            "selection_count": len(selections),
            "unique_record_count": len(records),
            "duplicate_selection_count": len(selections) - len(records),
            "records_by_media_kind": dict(sorted(Counter(
                r["media_kind"] for r in records).items())),
        },
        "limitations": [
            "Explicitly selected local artwork files only, at most 12 per run.",
            "Each analyzer retains its own format, duration, size and method limits.",
            "Any invalid input aborts the collection; no partial result is emitted.",
            "Deduplication is media kind plus raw-byte SHA-256, not perceptual or semantic equivalence.",
            "Distinct encodings of the same artwork may remain separate records.",
            "Report hashes describe serialized content, not authenticated provenance.",
            "No raw media, lyric quotations, file paths or inferred personal attributes in the catalog.",
            "No directory scanning, network, database, automatic linking, revision history or production integration.",
            "The caller may explicitly redirect the transient report to a local file.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--item", nargs=2, action="append", required=True,
                        metavar=("KIND", "PATH"),
                        help="Repeat for explicitly selected image, audio or lyrics artwork")
    args = parser.parse_args(argv)
    try:
        report = creative_archive(args.item)
    except (OSError, ValueError, EOFError, wave.Error,
            Image.DecompressionBombError) as exc:
        parser.exit(2, "Collection failed: " + str(exc) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
