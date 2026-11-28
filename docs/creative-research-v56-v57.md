# Creative research v5.6–v5.7

Base: v5.5 owner-reported Termux 1093 passed, 310 subtests, 1 Windows-only skip.

## Implemented
- PCM: exact integer accumulation across 16384-frame chunks; same result schema and normalization; up to 600 seconds, 16-bit mono/stereo 8–96 kHz. Memory used for sample buffers is bounded by chunk size, not file duration. Not a measured peak-RSS claim. No LUFS, true peak or automatic audio acquisition.
- Lyrics: MATTR windows 10/25/50, null for short texts, line token counts, adjacent orthographic initial matches. Tokenization is unchanged; no phonetic or semantic claims. Source: Covington & McFall (2010), DOI 10.1080/09296171003643098.
- HTML: exposes new lexical measurements. Inputs remain explicit local music and lyric files. No new services or dependencies.
- 13 new test methods: long file, chunk invariance, truncation, duration bound, unchanged input, brute-force MATTR reference, orthographic counts.

## Parallel review agenda (not implemented here)
- Audio: compare reference music files against EBU R128 (https://tech.ebu.ch/publications/r128); sample peak and RMS are not LUFS or true peak.
- Text: evaluate Finnish tokenization, pronunciation and rhyme annotation on manually reviewed creative fixtures; no author profiling.
- Art: check color and symmetry metrics on known test images; document aesthetic interpretation limits.
- Memory: synthetic correction and privacy regression review, distinguish service-level evidence from end-to-end assurance.
- Research: preserve source licensing and versions; record uncertainty and negative outcomes.
- UI: accessible static reports; review browser output separately from generation.
- Neurobiology/EEG: literature review and public educational examples only; no equivalence to consciousness claimed.
- Council72: review existing synthetic evaluation evidence and human rubric validity; no new autonomous execution.
- Release: review stacked draft PRs in dependency order, verify CI, document the Windows skip and AnyIO warning; no merge performed.

No live user data, external acquisition, new agent abilities, or persistent writes by the added analysis functions. Runtime and performance tests pending.
