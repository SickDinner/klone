"""Combine descriptive lyrics and music PCM measurements for a single song.

Explicit local files only. No network, model calls, audio recognition,
personal inference or persistent writes.
"""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import wave

from .lyrics_metrics import analyze_lyrics, MAX_BYTES
from .music_pcm_metrics import analyze_music_wav


def song_report(lyrics_path: Path, audio_path: Path) -> dict:
    with lyrics_path.open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Lyrics exceed byte limit")
    lyrics = analyze_lyrics(raw.decode("utf-8"))
    audio = analyze_music_wav(audio_path)
    return {
        "schema": "klone.song_report.v1",
        "lyrics": lyrics,
        "audio": audio,
        "limitations": [
            "Independent descriptive measurements of supplied files.",
            "No verification that the lyrics match the audio.",
            "No artistic quality, author identity or perceptual loudness inference.",
            "Section labels and text digest are not anonymized data.",
        ],
    }


def render_song_html(report: dict) -> str:
    def table(title, rows):
        return ("<h2>" + escape(title) + "</h2><table><tbody>"
                + "".join("<tr><th scope='row'>" + escape(str(key))
                          + "</th><td>" + escape(str(value)) + "</td></tr>"
                          for key, value in rows)
                + "</tbody></table>")

    lyrics, audio = report["lyrics"], report["audio"]
    body = table("Lyrics", [(key, lyrics[key]) for key in (
        "line_count", "word_count", "unique_word_count",
        "type_token_ratio", "repeated_line_occurrences")])
    body += table("Lexical diversity (MATTR)", [
        (key + " tokens", value if value is not None else "Insufficient tokens")
        for key, value in lyrics["mattr"].items()
    ])
    body += table("Orthographic patterns", [
        ("Adjacent initial-letter matches", lyrics["adjacent_initial_matches"]),
        ("Eligible adjacent word pairs", lyrics["adjacent_word_pairs"]),
    ])
    for distance, stats in lyrics.get("orthographic_end_patterns", {}).items():
        body += table("Written line endings (distance " + distance + ")", list(stats.items()))
    body += table("Sections", [(section["label"],
                                f"{section['line_count']} lines, {section['word_count']} words")
                               for section in lyrics["sections"]])
    body += table("Audio", [(key, audio[key]) for key in (
        "sample_rate_hz", "frames", "duration_seconds")])
    for channel in audio["channels"]:
        body += table("Channel " + str(channel["channel"] + 1),
                      [(key, channel[key]) for key in (
                          "peak", "rms", "mean", "zero_fraction", "full_scale_fraction")])
        if "one_second_rms" in channel:
            body += table("Channel " + str(channel["channel"] + 1) + " dynamics", [
                ("Crest factor (dB)", channel["crest_factor_db"]),
                *channel["one_second_rms"].items(),
            ])
    limitations = report["limitations"] + lyrics["limitations"] + audio["limitations"]
    body += "<h2>Limitations</h2><ul>" + "".join(
        "<li>" + escape(item) + "</li>" for item in limitations) + "</ul>"
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>KLONE song report</title><style>"
        "body{font:16px system-ui,sans-serif;max-width:54rem;margin:2rem auto;padding:0 1rem}"
        "table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:.5rem;"
        "border-bottom:1px solid #888;overflow-wrap:anywhere}"
        "</style></head><body><main><h1>KLONE song report</h1>"
        + body + "</main></body></html>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lyrics", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--format", choices=("json", "html"), default="json")
    args = parser.parse_args(argv)
    try:
        report = song_report(args.lyrics, args.audio)
    except (ValueError, OSError, EOFError, wave.Error) as exc:
        parser.error(str(exc))
    if args.format == "html":
        print(render_song_html(report))
    else:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
