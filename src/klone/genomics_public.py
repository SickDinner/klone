"""Offline, public-only genomic sample catalog and conservative comparison.

No individual genotype, DNA sequence, inferred ethnicity, medical interpretation,
or network access. Explicit assembly, assay, source and consent gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json


@dataclass(frozen=True)
class PublicSample:
    accession: str
    source: str
    publication: str
    assembly: str
    assay: str
    region: str
    period_start_ce: int
    period_end_ce: int
    public_release: bool
    reuse_permitted: bool
    quality: str
    y_haplogroup: str | None = None
    mt_haplogroup: str | None = None


def validate_public_sample(sample: PublicSample) -> None:
    if not isinstance(sample, PublicSample):
        raise ValueError("Expected PublicSample")
    for name in ("accession", "source", "publication", "assembly", "assay", "region", "quality"):
        value = getattr(sample, name)
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise ValueError("Invalid sample metadata: " + name)
    if sample.public_release is not True or sample.reuse_permitted is not True:
        raise PermissionError("Public release and reuse permission are required")
    if type(sample.period_start_ce) is not int or type(sample.period_end_ce) is not int:
        raise ValueError("Invalid chronology")
    if not -100000 <= sample.period_start_ce <= sample.period_end_ce <= 2100:
        raise ValueError("Invalid chronology")
    if sample.assembly not in {"GRCh37", "GRCh38"}:
        raise ValueError("Unknown reference assembly")
    if sample.assay not in {"1240k", "shotgun", "WGS", "capture", "mtDNA", "Y-DNA"}:
        raise ValueError("Unknown assay")
    if sample.quality not in {"low", "medium", "high", "unknown"}:
        raise ValueError("Unknown quality")
    for name in ("y_haplogroup", "mt_haplogroup"):
        value = getattr(sample, name)
        if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 128):
            raise ValueError("Invalid haplogroup metadata")


def catalog_fingerprint(samples: tuple[PublicSample, ...]) -> str:
    """Order-independent provenance fingerprint; duplicate accessions rejected."""
    if not isinstance(samples, tuple):
        raise ValueError("Expected tuple")
    for sample in samples:
        validate_public_sample(sample)
    keys = [(s.source, s.accession) for s in samples]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate source accession")
    from dataclasses import asdict
    rows = sorted((asdict(s) for s in samples), key=lambda row: (row["source"], row["accession"]))
    payload = json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def compare_public_metadata(left: PublicSample, right: PublicSample) -> dict[str, object]:
    """Compare metadata only; haplogroup equality never proves close kinship."""
    validate_public_sample(left)
    validate_public_sample(right)
    compatible = left.assembly == right.assembly and left.assay == right.assay
    overlap = max(left.period_start_ce, right.period_start_ce) <= min(left.period_end_ce, right.period_end_ce)
    return {
        "assembly_compatible": left.assembly == right.assembly,
        "assay_compatible": left.assay == right.assay,
        "direct_genotype_comparison_ready": False,
        "metadata_comparable": compatible,
        "date_ranges_overlap": overlap,
        "y_label_equal": bool(left.y_haplogroup and right.y_haplogroup and left.y_haplogroup == right.y_haplogroup),
        "mt_label_equal": bool(left.mt_haplogroup and right.mt_haplogroup and left.mt_haplogroup == right.mt_haplogroup),
        "kinship_inference": "not_supported_by_metadata",
    }
