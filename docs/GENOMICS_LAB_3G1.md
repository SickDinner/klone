# Genomics Lab 3G.1: public research catalog

This is a safe offline metadata foundation, **not** a genome analysis engine.

## Source adapters planned

- AADR: ancient genotype metadata and public 1240k/2M panel release, subject to each release's documentation and reuse terms.
- ENA / NCBI SRA: public accession metadata; never assume a public landing page makes individual-level reads redistributable.
- dbSNP and Ensembl VEP: variant identifiers and functional annotation. VEP predicts consequences; it does not establish disease diagnosis.
- EGA: controlled access only. No automatic ingest.

## Data governance

The `PublicSample` record must carry explicit release and reuse permission flags, source, publication, assembly, assay, temporal interval and quality. These flags are validated assertions by a trusted importer, **not** a license checker. An untrusted agent must not set them itself. No actual genomes, names, raw DNA, individual-level variant lists or private DNA are accepted in this phase.

Never combine GRCh37/GRCh38 coordinates or 1240k/shotgun assays without explicit normalization and QC. Haplogroup labels are metadata, not proof of close family relationships. Ancient dates have uncertainty; intervals represent declared bounds, not calibrated radiocarbon likelihoods.

## Next gated phases

1. Source-specific importer, manifest hashes, license checks and explicit data-use records.
2. Separate restricted Genomics room and owner-authorized private genome import; encryption at rest, key separation and retention controls.
3. Reference-assembly normalization, missingness and contamination QC, allele harmonization and reproducible pipelines.
4. Population statistics with uncertainty, reference-panel ascertainment and sample-size checks.
5. Evidence Ledger integration only after authenticated Hypervisor approval and atomic audit.

No external API calls, downloads, ingestion or health/ancestry inference are performed by this module.
