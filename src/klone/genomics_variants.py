"""Offline variant harmonization quality gate; no ancestry or medical inference.

Variant coordinates are 1-based; the reference assembly must be explicit.
Only simple SNVs are supported. This deliberately does not liftover builds,
resolve strand flips, infer genotype or compare individuals.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json


@dataclass(frozen=True)
class VariantSite:
    assembly: str
    chromosome: str
    position: int
    reference: str
    alternate: str
    source_accession: str


def normalize_snv(site: VariantSite) -> VariantSite:
    if not isinstance(site, VariantSite):
        raise ValueError("Expected VariantSite")
    if site.assembly not in ("GRCh37", "GRCh38"):
        raise ValueError("Unsupported assembly")
    if type(site.position) is not int or not 1 <= site.position <= 300_000_000:
        raise ValueError("Invalid 1-based coordinate")
    chromosome = site.chromosome.removeprefix("chr") if isinstance(site.chromosome, str) else ""
    if chromosome not in {*map(str, range(1, 23)), "X", "Y", "MT"}:
        raise ValueError("Invalid chromosome")
    if not isinstance(site.reference, str) or not isinstance(site.alternate, str):
        raise ValueError("Invalid alleles")
    reference, alternate = site.reference.upper(), site.alternate.upper()
    if reference not in "ACGT" or alternate not in "ACGT" or reference == alternate:
        raise ValueError("Only non-identical A/C/G/T SNVs supported")
    if not isinstance(site.source_accession, str) or not site.source_accession.strip() or len(site.source_accession) > 256:
        raise ValueError("Missing source provenance")
    return VariantSite(site.assembly, chromosome, site.position, reference, alternate, site.source_accession)


def harmonize_sites(sites: tuple[VariantSite, ...]) -> dict[str, object]:
    """Return deterministic site inventory and conflict diagnostics.

    This checks structural compatibility only, not allele correctness
    against a FASTA reference or individual genotype concordance.
    """
    if not isinstance(sites, tuple) or len(sites) > 100_000:
        raise ValueError("Invalid or oversized batch")
    normalized = tuple(normalize_snv(s) for s in sites)
    assemblies = {s.assembly for s in normalized}
    if len(assemblies) > 1:
        raise ValueError("Mixed genome assemblies require explicit liftover")
    loci: dict[tuple[str, int], set[tuple[str, str]]] = {}
    for s in normalized:
        loci.setdefault((s.chromosome, s.position), set()).add((s.reference, s.alternate))
    conflicts = sorted(f"{chrom}:{pos}" for (chrom, pos), alleles in loci.items() if len(alleles) > 1)
    rows = sorted({(s.assembly, s.chromosome, s.position, s.reference, s.alternate, s.source_accession)
                   for s in normalized})
    digest = sha256(json.dumps(rows, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "assembly": next(iter(assemblies)) if assemblies else None,
        "input_count": len(sites),
        "unique_records": len(rows),
        "conflicting_loci": tuple(conflicts),
        "reference_fasta_verified": False,
        "strand_verified": False,
        "genotype_comparison_ready": False,
        "fingerprint": digest,
    }
