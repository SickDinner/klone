# Offline research laboratory: v4.1–v4.9

Base: v4.0, owner-reported 1031 passed and 300 subtests. This draft is test-only.

| Track | Present deliverable | Next validation |
| --- | --- | --- |
| 4.1 Review quality | Categorical agreement on human-supplied synthetic labels | Distinguish agreement, accuracy and uncertainty; independent human review |
| 4.2 Neurochemical analogies | Research protocol only | Preregister simple nonadaptive toy models; no biological equivalence claims |
| 4.3 Knowledge | Synthetic version and digest checks | Licensed public art and science sources, explicit provenance and dates |
| 4.4 Memory consolidation | Research protocol only | Compare archival summaries against synthetic source records, without writes to real memory |
| 4.5 Multimedia | Actual image metrics and standard-library WAV fixture | Test consented media with separate review; no voice cloning or biometric inference |
| 4.6 Mission Control | Report serialization check | Read-only display of verified test results |
| 4.7 Performance | Existing image sample bound check | Report wall time, environment and peak memory separately; no hard timing assertions |
| 4.8 Reproducibility | JSON round trips and content digests | Pin dependencies and distinguish deterministic data from timing |
| 4.9 Integration | Shared offline test suite | Full regression with optional signature backend and platform skips reported |

Run: python -m pytest -q tests/test_offline_research_lab_v41_v49.py

14 test methods, including two cases of invalid review input. No production changes, autonomous agents, model calls, external retrieval, real personal data or permission changes. Audio fixture tests Python WAV handling, not a KLONE audio pipeline. Image checks call the existing implementation. Hashes establish byte-level consistency under this serialization rule, not truth or authenticity. Review agreement is not an assessment of real Council72 output. No experimental neurochemical or dream module is implemented. Runtime checks pending.
