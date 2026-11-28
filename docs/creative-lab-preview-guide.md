# KLONE Creative Laboratory — preview guide (draft)

This document describes the creative research tools in the development snapshot
bdbf12d630a0966d2085a9b8ceecc9f879c12609. It is not a software release, a
statement of open-source licensing, or an installation guide for the full system.

## Scope

The preview concerns local descriptive artwork, musical signal, written verse
and mathematical art demonstrations. It does not include other KLONE services.
The tools do not establish consciousness, aesthetic merit, identity, clinical
outcomes or semantic correspondence between different creative files.

## Observed results, 2026-11-28

The owner reported 1225 passing primary tests, 348 passing subtests, one
Windows-specific skip and one existing Starlette/AnyIO deprecation warning.
Elapsed time: 121.47 seconds on Android/Termux. Both associated GitHub Actions
workflows completed successfully. This is not an independent clean-install
verification. The overall test count is for the development tree, not a count
of creative laboratory features.

## Supported inputs

| Input | Limits |
| --- | --- |
| Artwork | Single-frame PNG/JPEG, at most 4,000,000 source pixels; sampled at up to 128 x 128 |
| Palette histogram | 512 possible encoded RGB bins; complete counts optional |
| Audio dynamics | Mono/stereo 16-bit PCM WAV, 8–96 kHz, nonempty, at most 600 seconds |
| Leading spectrum | Same PCM format, at least 1024 frames; up to 32 complete 1024-frame windows |
| Lyrics | UTF-8, at most 256,000 bytes and 10,000 lines |
| Mathematical art | Regular polygons with 3–72 sides |

Encoded RGB is not a perceptual color space. A leading-clip spectrum is not a
full-track analysis. Written vowel groups are not phonetic syllables.
Unavailable values are not measurements of zero.

## Demonstrations in an existing authorized development environment

These examples use already available local creative modules. They do not
install or start other KLONE services.

- `python -m klone.mathematical_art --sides 72 --format svg` outputs a regular polygon.
- `python -m klone.abstract_gallery --format html` outputs a synthetic abstract-art comparison.
- `python -m klone.artwork_palette_entropy BEFORE.png AFTER.png` compares sampled artwork color distributions.
- `python -m klone.creative_prism --artwork ART.png --music MUSIC.wav --lyrics LYRICS.txt` outputs five separate descriptive perspectives.

The supplied filenames are placeholders for explicitly selected creative files.
Use only files you have permission to process. Reports may contain labels or
other derived information; review their contents before sharing.

## Release gates

| Gate | Status |
| --- | --- |
| Owner Android regression | Observed pass |
| GitHub CI at snapshot | Observed pass |
| Creative dashboard mobile screenshots | Previously observed for v7.1 |
| v7.5 gallery browser visual review | Pending |
| v7.7 SVG visual review | Pending |
| Clean standalone environment | Pending |
| Desktop and assistive technology review | Pending |
| Dependency and redistribution review | Pending |
| License for selected files | Unconfirmed |
| Release artifact and release authorization | Not completed |

The repository is publicly visible, but public visibility alone does not grant
an open-source license. LICENSE, LICENSE.md and COPYING were not found at the
root of the inspected snapshot; a license elsewhere has not been ruled out.
The maintainer must establish the actual applicable licensing terms before
distributing a software package. No license is selected by this document.

Project Python metadata requires Python >=3.11 and Pillow >=13,<14. These
requirements do not demonstrate that every supported platform works. No claim
of a standalone packaged creative application is made here.

## What comes next

Prefer a review of the existing creative demonstration and its documentation
over adding more features solely to increase regression counts. Resolve the
remaining gates before proposing a separate distributable preview.
