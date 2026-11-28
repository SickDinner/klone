# Creative Laboratory v6.1–v7.0

Baseline: v6.0 commit abc8539cbf33bd0aa1e9ee5357247829855719d7.
Owner-reported Android regression: 1128 passed, 323 subtests, one Windows-only skip and one existing deprecation warning.

## Delivered in this branch

- v6.1: sampled RGB histogram of explicitly supplied PNG/JPEG artwork; 4 million pixel input limit; 128 pixel sample side, eight leading bins. Encoded RGB is not a perceptual color space; no semantic image analysis.
- v6.2: short music clip spectrum, first 32 complete 1024-frame periodic Hann windows at most. Mean removed per window, one-sided power weights, per-channel band fractions and spectral centroid. Only the leading analyzed clip is measured; bands above Nyquist contain no observed frequency bins. Not standardized loudness, tempo or whole-track spectrum.
- v6.3: contiguous written Finnish vowel groups per lyric line. Orthographic proxy only, not syllabification or meter classification.
- v6.4: total-variation comparison of complete sampled color histograms produced by v6.1. No comparison when top-eight truncation removes bins; not perceptual color distance.
- v6.5: one local JSON report from three explicitly supplied creative files. No claim that they describe the same subject. CLI reads only these files, with no new services or persistent writes.
- 19 synthetic test methods, including direct DFT reference, known musical tone, transparent artwork, Unicode equivalence and incomplete histogram handling.

Run targeted tests:
python -m pytest -q tests/test_creative_lab_v61_v63.py tests/test_creative_project_v64_v65.py

Run the report with your own creative files:
python -m klone.creative_project_report --artwork art.png --music-clip music.wav --lyrics lyrics.txt

## Remaining release gates (not delivered here)

- v6.6: accessible static research-history presentation; distinguish owner-reported observations, CI and missing results.
- v6.7: review existing synthetic memory correction/privacy regression coverage, including limits of service-level tests; no new agent execution.
- v6.8: controlled resource benchmarks for creative fixtures, report environment, multiple repetitions, wall time and peak memory separately.
- v6.9: independent reviewed reference fixtures, known limitations and negative results; validate before claiming perceptual or linguistic accuracy.
- v7.0: review stacked changes and exact dependency chain; repeat relevant regression and platform checks, review warnings, documentation, privacy and release scope. No release or merge here.

No new dependencies, network use, automatic data discovery, model calls, live personal data or production service changes. The modules are local creative research tools. Runtime verification pending. Established mathematical methods are used, not claimed to be novel or state-of-the-art.
