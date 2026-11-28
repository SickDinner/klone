# KLONE creative research innovation agenda

Baseline: v7.0 RC a551f4084344a5bc834c45ffbf32e7fb01e558f3.
Owner-reported Android regression: 1163 passed, 333 subtests, one Windows-specific skip, one existing dependency warning. Mobile research-history cards visually confirmed in owner screenshots.

## Delivered in v7.1
Responsive static dashboard for explicitly supplied creative project reports. Three panels: sampled artwork colors, leading music-clip spectral measurements, and written verse rhythm proxies. Text labels accompany colors and numerical meters; unavailable values remain distinct from zero. Existing JSON output remains default. No external assets, new dependencies, model calls, autonomous execution, or production changes. Eight synthetic tests; device rendering and regression pending.

## Research candidates (not implemented)
- W3C WCAG-EM 2.0 (23 July 2026), https://www.w3.org/TR/WCAG-EM/ : evaluation protocol for mobile/desktop and assistive technology. WCAG 3.0 is still a working draft, not an achieved compliance target.
- ISMIR 2026 tutorials and MIREX 2026: https://ismir2026.ismir.net/tutorials and https://music-ir.org/mirex/wiki/MIREX_HOME : use reviewed musical reference fixtures; compare errors against declared reference annotations before adding claims about tempo or structure.
- IncompeBench preprint, https://arxiv.org/abs/2602.11941 : examine permissively licensed fine-grained music annotations and verify actual license and dataset availability before use.
- Finnish morphology: HFST, https://www.kielipankki.fi/tools/hfst/ ; Omorfi v0.9.12 (January 2026), https://zenodo.org/records/18149491 . Test optional morphology against manually annotated Finnish verses, including dialect and creative neologisms. Do not overwrite originals.
- RO-Crate 1.3, https://www.researchobject.org/ro-crate/specification/1.3/introduction.html : consider interoperable export of explicitly selected creative research materials with licenses and measurement versions. No automatic collection or publication. Do not claim compatibility until validated.
- Open neuroscience education: BIDS and OpenNeuro https://bids.neuroimaging.io/index and https://openneuro.org/ . Literature and openly licensed teaching examples only; no individual inference, clinical claims or brain-control systems.

## Experimental concepts
- Creative prism: parallel numerical, visual and human-written interpretations of a single work, never collapsed to one artistic quality score.
- Counterfactual gallery: change only one artistic variable in a synthetic fixture, then compare before/after metrics and human judgments.
- Lost-works atlas: owner-curated versions, incomplete works and explicitly marked gaps; preserve alternative interpretations and source provenance.
- Negative result museum: retain failed creative hypotheses and documented uncertainty rather than hiding them.
- Nordic language workshop: compare licensed Finnish and Swedish poetry examples; treat linguistic variation as variation rather than errors.
- Evidence exhibition: publish only selected non-sensitive research artifacts with clear licenses and limitations.
- Council72 as a manually curated creative critique rubric with different aesthetic schools; not an autonomous operating system or authority over the user.
- Dream gallery: fictional art and story prompts, explicitly separated from factual records.
- Accessible research studio: mobile-first static cards, screen-reader-friendly text alternatives and keyboard navigation, reviewed on real devices.

## Acceptance gates
Run targeted and full regression on exact commit. Check real narrow-screen output and desktop layout separately. Preserve old reports and source files. Evaluate hypotheses on independent human-reviewed fixtures; describe failure and unavailable results. No claim of universal performance, consciousness, medical utility, or validated artistic quality. No merge or release in this branch.
