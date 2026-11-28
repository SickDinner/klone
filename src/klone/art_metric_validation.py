"""Controlled synthetic checks of the local creative-art descriptors.

Temporary fixtures only. These checks establish selected numerical properties,
not empirical human-perception validity or artistic merit.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import struct
import tempfile
import wave

from PIL import Image
from .local_art_image_study import analyze_image
from .local_art_audio_study import analyze_audio
from .local_art_lyrics_study import analyze_lyrics

TOLERANCE = 1e-9


def validation_study():
    checks = []

    def check(identifier, domain, observed, expected, scope):
        def equal(a, b):
            if b is None or isinstance(b, bool):
                return a is b
            if isinstance(b, (int, float)):
                return isinstance(a, (int, float)) and not isinstance(a, bool) and math.isclose(
                    a, b, rel_tol=0, abs_tol=TOLERANCE)
            return a == b

        passed = (observed.keys() == expected.keys() and
                  all(equal(observed[k], v) for k, v in expected.items()))
        checks.append({"id": identifier, "domain": domain,
                       "status": "passed" if passed else "failed",
                       "observed": observed, "expected": expected,
                       "scope": scope})

    with tempfile.TemporaryDirectory(prefix="klone-art-validation-") as tmp:
        root = Path(tmp)

        def image(name, row, repeat=1):
            p = root / (name + ".png")
            im = Image.new("RGB", (len(row)*repeat, 8*repeat))
            im.putdata([(255*v,)*3 for v in row for _ in range(repeat)] * (8*repeat))
            im.save(p)
            return analyze_image(p)["metrics"]

        split = image("split", [0,0,0,0,1,1,1,1])
        centered = image("centered", [0,0,1,1,1,1,0,0])
        enlarged = image("enlarged", [0,0,0,0,1,1,1,1], 2)
        check("image_equal_distribution", "image",
              {"mean_difference": centered["mean_relative_luminance"]-split["mean_relative_luminance"],
               "contrast_difference": centered["luminance_population_sd"]-split["luminance_population_sd"],
               "entropy_difference": centered["rgb_bin_entropy_bits"]-split["rgb_bin_entropy_bits"]},
              {"mean_difference":0,"contrast_difference":0,"entropy_difference":0},
              "Equal black/white proportions despite different spatial placement.")
        check("image_reflection_distinguishes", "image",
              {"split":split["left_right_luminance_reflection_error"],
               "centered":centered["left_right_luminance_reflection_error"]},
              {"split":1,"centered":0},
              "Two specific binary patterns; not general perceptual similarity.")
        check("image_integer_replication", "image",
              {k:enlarged[k]-split[k] for k in ("mean_relative_luminance",
               "luminance_population_sd","rgb_bin_entropy_bits",
               "left_right_luminance_reflection_error")},
              dict.fromkeys(("mean_relative_luminance","luminance_population_sd",
                             "rgb_bin_entropy_bits","left_right_luminance_reflection_error"),0),
              "Nearest pixel replication below thumbnail limit; not arbitrary resizing.")

        def audio(name, values):
            p = root / (name + ".wav")
            with wave.open(str(p), "wb") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(8192)
                f.writeframes(struct.pack("<"+"h"*len(values), *values))
            return analyze_audio(p)

        quiet = audio("quiet",[0,8192,0,-8192]*256)
        loud = audio("loud",[0,16384,0,-16384]*256)
        silent = audio("silent",[0]*1024)
        q, l, s = (r["channel_metrics"][0] for r in (quiet,loud,silent))
        check("audio_exact_gain", "audio",
              {"peak_ratio":l["peak"]/q["peak"],"rms_ratio":l["rms"]/q["rms"],
               "crest_difference":l["crest_factor"]-q["crest_factor"]},
              {"peak_ratio":2,"rms_ratio":2,"crest_difference":0},
              "Exactly scaled integer samples without saturation.")
        check("audio_centroid_gain_invariance", "audio",
              {"quiet_hz":quiet["sampled_spectrum"]["power_centroid_hz"],
               "loud_hz":loud["sampled_spectrum"]["power_centroid_hz"]},
              {"quiet_hz":2048,"loud_hz":2048},
              "One FFT-bin-aligned tone, not arbitrary recordings or gain processing.")
        check("audio_silence_missingness", "audio",
              {"rms":s["rms"],"crest_factor":s["crest_factor"],
               "centroid":silent["sampled_spectrum"]["power_centroid_hz"],
               "bands":silent["sampled_spectrum"]["band_power_fractions"]},
              {"rms":0,"crest_factor":None,"centroid":None,"bands":None},
              "All-zero samples; absence of sampled power differs from zero frequency.")

        def lyrics(name, text):
            p = root / (name + ".txt")
            p.write_text(text, encoding="utf-8")
            return analyze_lyrics(p)

        base = lyrics("base","Yö saapuu\nTuuli kulkee\n")
        repeated = lyrics("repeated","Yö saapuu\nTuuli kulkee\n\nYö saapuu\nTuuli kulkee\n")
        normalized = lyrics("normalized","YO\u0308 SAAPUU!\nTUULI KULKEE?\n")
        b, r, n = (v["lexical_metrics"] for v in (base,repeated,normalized))
        check("lyrics_normalization", "lyrics",
              {"equal_lexical_metrics":b==n,
               "equal_source":base["source"]["sha256"]==normalized["source"]["sha256"]},
              {"equal_lexical_metrics":True,"equal_source":False},
              "Case, NFC and punctuation changes in this fixture; not semantic equivalence.")
        check("lyrics_ttr_length_sensitivity", "lyrics",
              {"base_ttr":b["type_token_ratio"],"repeated_ttr":r["type_token_ratio"],
               "distinct_difference":r["distinct_word_forms"]-b["distinct_word_forms"],
               "repeated_line_fraction":r["repeated_normalized_line_fraction"]},
              {"base_ttr":1,"repeated_ttr":.5,"distinct_difference":0,"repeated_line_fraction":.5},
              "Exact repetition lowers TTR without changing the vocabulary.")
        ends = lyrics("ends","Kissa\nPissa\nPissa\nMissä\n")["line_end_metrics"]
        check("lyrics_suffix_vs_identity", "lyrics",
              {"eligible":ends["eligible_adjacent_end_pairs"],
               "distinct_matches":ends["distinct_end_word_suffix_matches"],
               "identical":ends["identical_end_word_pairs"]},
              {"eligible":3,"distinct_matches":1,"identical":1},
              "Three-character written suffix rule; not validated phonological rhyme.")
        empty = lyrics("empty","")["lexical_metrics"]
        check("lyrics_empty_missingness", "lyrics",
              {"words":empty["word_count"],"ttr":empty["type_token_ratio"],
               "initial_fraction":empty["adjacent_initial_match_fraction"]},
              {"words":0,"ttr":None,"initial_fraction":None},
              "Empty input has zero words but undefined ratios.")

    return {
        "schema":"klone.art_metric_validation.v1",
        "checks":checks,
        "status_counts":dict(sorted(Counter(c["status"] for c in checks).items())),
        "absolute_tolerance":TOLERANCE,
        "scope":{"synthetic_only":True,"empirical_observer_validation":False,
                 "overall_quality_score":None},
        "limitations":[
            "Ten predeclared controlled checks; not independent experiments.",
            "Only small synthetic artworks; no real media or personal data.",
            "Expected values are analytic properties of selected fixtures, not observer ratings.",
            "No general invariance claim outside the stated fixture conditions.",
            "Temporary synthetic files are removed after the run; no production integration.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    report = validation_study()
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 1 if report["status_counts"].get("failed",0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
