# Creative laboratory V12.1 architecture review

Scope: the isolated local artwork research modules through V11.8, not the
production KLONE system. Review findings are based on source inspection and
the owner-reported Android verification of V11.8 (1590 tests passed).

## Finding and correction

V11.8 built its collection, then independently reopened the paths in each
comparison. If a selected artwork changed between these operations, the
comparison could refer to a report different from the one in the collection.
The test suite checked determinism with stable inputs but did not cover this
case. V12.1 resolves comparison endpoints to captured collection records,
requires both endpoints to be explicitly selected with the same medium and
path spelling, and rejects repeated identical selection keys whose captured
source fingerprints differ. The standalone pair-comparison CLI retains its
existing behavior.

This is report-level consistency, not an atomic filesystem snapshot. Different
files may still be read at different times, and a file may be modified during a
read. Filesystem aliases are not automatically resolved. Record hashes are
content fingerprints, not signatures or proof of authorship.

## Presentation

Expose each artwork's existing method limitations, comparison notes, and
synthetic validation totals directly in the HTML. Keep original JSON payloads,
escape displayed values, and retain the static offline report architecture.

## Remaining limitations and priorities

- Image: thumbnail resampling, assumed sRGB and encoded-RGB alpha compositing
  limit colorimetric conclusions; no ICC conversion or observer validation.
- Music: sampled rectangular FFT windows may miss events or leak spectral
  energy; the final nominal 100 ms envelope block can be shorter. Report
  digital levels, not perceived loudness. No whole-song tempo estimate.
- Lyrics: written vowel groups are not syllables, suffix matches are not
  phonetic rhymes, and TTR depends on length. Finnish linguistic validation
  and explicit exceptions should precede stronger interpretations.
- Collection: explicit bounded selections only; no durable revision history,
  inferred chronology, automatic file discovery, or general-purpose memory.
- HTML: structural tests are not a substitute for actual Android browser
  inspection, keyboard navigation checks or screen reader review.
- Testing: synthetic fixtures support only their declared scope. No empirical
  evidence of artistic quality, human perception or personal attributes.
- Runtime: one existing Starlette deprecation warning and one Windows-specific
  skipped test were reported in V11.8; dependency changes are outside this PR.

## Acceptance criteria

Existing V11.8 tests remain green. New tests cover no comparison rereads,
membership and medium checks, repeated-selection conflict handling, exact
self-comparison, visible caveats, compatibility with standalone comparisons,
and failure without partial HTML for unselected inputs. Verify on the pinned
Termux checkout before claiming runtime success. No production integration or
branch merge is part of this change.
