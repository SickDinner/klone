"""Static, local presentation of descriptive creative project measurements."""
from __future__ import annotations

from html import escape
import math


def _percentage(value):
    if value is None:
        return "Not available"
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Invalid fraction")
    return f"{value * 100:.2f}%"


def _swatch(rgb_bin):
    if not isinstance(rgb_bin, list) or len(rgb_bin) != 3 or any(
        type(x) is not int or not 0 <= x <= 7 for x in rgb_bin
    ):
        raise ValueError("Invalid RGB bin")
    color = "#" + "".join(f"{x * 32 + 16:02x}" for x in rgb_bin)
    return "<span class='swatch' aria-hidden='true' style='background:" + color + "'></span>"


def render_creative_dashboard(report: dict) -> str:
    if report["schema"] != "klone.creative_project_report.v1":
        raise ValueError("Unsupported creative report schema")

    def text(value):
        return escape(str(value)) if value is not None else "Not available"

    def metric(label, value):
        return "<div><dt>" + text(label) + "</dt><dd>" + text(value) + "</dd></div>"

    def metrics(items):
        return "<dl class='metrics'>" + "".join(metric(k, v) for k, v in items) + "</dl>"

    art, audio, verse = (report[k] for k in ("artwork", "music_clip", "verse"))
    palette = "".join(
        "<li>" + _swatch(b["rgb_bin"]) + "<span>RGB bin "
        + text(b["rgb_bin"]) + "</span><strong>" + _percentage(b["fraction"]) + "</strong></li>"
        for b in art["dominant_bins"]
    )
    art_body = metrics([
        ("Sample dimensions", " × ".join(str(x) for x in art["sample_dimensions"])),
        ("Neutral fraction", _percentage(art["neutral_fraction"])),
        ("Occupied bins", art["occupied_rgb_bins"]),
    ]) + "<h3>Leading color bins</h3><ul class='palette'>" + palette + "</ul>"

    audio_body = metrics([
        ("Sample rate (Hz)", audio["sample_rate_hz"]),
        ("Analyzed frames", audio["analyzed_frames"]),
        ("Declared source frames", audio["source_declared_frames"]),
        ("Complete windows", audio["windows"]),
    ])
    for channel in audio["channels"]:
        audio_body += "<h3>Channel " + text(channel["channel"] + 1) + "</h3>"
        audio_body += metrics([("Power centroid (Hz)", channel["spectral_centroid_hz"])])
        audio_body += "<ul class='bands'>"
        for band in channel["band_fractions"]:
            label = f'{band["low_hz"]}–{band["high_hz_exclusive"]} Hz'
            value = band["fraction"]
            percent = _percentage(value)
            audio_body += "<li><span>" + text(label) + "</span><strong>" + percent + "</strong>"
            if value is not None:
                audio_body += "<meter min='0' max='1' value='" + str(float(value)) + "' aria-label='" + text(label) + "'></meter>"
            audio_body += "</li>"
        audio_body += "</ul>"

    verse_body = metrics([
        ("Lines", verse["line_count"]),
        ("Mean written vowel groups", verse["mean_vowel_groups"]),
        ("Equal adjacent counts", verse["equal_adjacent_counts"]),
    ]) + "<h3>Written vowel-group histogram</h3><ul class='bands'>" + "".join(
        "<li><span>" + text(key) + " groups</span><strong>" + text(value) + " lines</strong></li>"
        for key, value in verse["vowel_group_histogram"].items()
    ) + "</ul>"
    notes = "".join("<li>" + text(note) + "</li>" for source in (report, art, audio, verse)
                    for note in source["limitations"])

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>KLONE Creative Laboratory</title><style>"
        ":root{color-scheme:light dark}*{box-sizing:border-box}"
        "body{font:16px/1.5 system-ui,sans-serif;max-width:75rem;margin:1rem auto;padding:0 1rem}"
        "h1{font-size:clamp(1.6rem,5vw,2.5rem);line-height:1.2}h2{margin-top:0}"
        ".laboratory{display:grid;gap:1rem}.panel{border:1px solid #888;border-radius:.75rem;"
        "padding:1rem;min-width:0;overflow-wrap:break-word}"
        ".metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem}"
        ".metrics>div{min-width:0;border-top:1px solid #888;padding-top:.4rem}"
        "dt{font-size:.85rem}dd{margin:0;font-size:1.15rem;font-weight:600}"
        ".palette,.bands{padding:0;list-style:none}.palette li,.bands li{display:flex;align-items:center;"
        "gap:.5rem;flex-wrap:wrap;padding:.4rem 0;border-bottom:1px solid #888}"
        ".palette strong,.bands strong{margin-left:auto}.swatch{width:1.5rem;height:1.5rem;"
        "border:1px solid #888;border-radius:.2rem;flex:none}meter{width:100%;height:.8rem}"
        "@media(min-width:64rem){.laboratory{grid-template-columns:repeat(3,minmax(0,1fr))}}"
        "@media(max-width:20rem){.metrics{grid-template-columns:1fr}}"
        "</style></head><body><main><h1>KLONE Creative Laboratory</h1>"
        "<p>Independent descriptive measurements of supplied creative files.</p>"
        "<div class='laboratory'><section class='panel'><h2>Artwork</h2>" + art_body
        + "</section><section class='panel'><h2>Music clip</h2>" + audio_body
        + "</section><section class='panel'><h2>Written verse</h2>" + verse_body
        + "</section></div><section><h2>Limitations</h2><ul>" + notes
        + "</ul></section></main></body></html>"
    )
