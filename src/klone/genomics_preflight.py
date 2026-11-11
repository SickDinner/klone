"""Offline VCF preflight for synthetic or explicitly supplied local bytes.

No persistence, annotation, subprocess, remote lookups, or data export.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

MAX_VCF_BYTES = 8 * 1024 * 1024
MAX_VARIANTS = 100_000
MAX_LINE_BYTES = 1_000_000


@dataclass(frozen=True)
class VcfPreflight:
    sha256: str
    reference_build: str
    sample_count: int
    variant_count: int
    contig_count: int


def preflight_vcf(data: bytes, *, reference_build: str) -> VcfPreflight:
    """Parse only VCF structure; never return sample IDs or variant values."""
    if not isinstance(data, bytes) or len(data) > MAX_VCF_BYTES or not data:
        raise ValueError("vcf_size_invalid")
    if reference_build not in {"GRCh37", "GRCh38"}:
        raise ValueError("reference_build_required")
    seen_fileformat = False
    seen_header = False
    contigs: set[str] = set()
    variant_count = 0
    sample_count = 0
    for raw in BytesIO(data):
        if len(raw) > MAX_LINE_BYTES:
            raise ValueError("vcf_line_too_large")
        try:
            line = raw.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError as error:
            raise ValueError("vcf_utf8_invalid") from error
        if line.startswith("##fileformat=VCFv"):
            if seen_fileformat or seen_header:
                raise ValueError("vcf_duplicate_fileformat")
            seen_fileformat = True
        elif line.startswith("##contig=<ID="):
            if seen_header:
                raise ValueError("vcf_metadata_after_header")
            contig = line[len("##contig=<ID="):].split(",", 1)[0].split(">", 1)[0]
            if not contig:
                raise ValueError("vcf_contig_invalid")
            contigs.add(contig)
        elif line.startswith("#CHROM\t"):
            if not seen_fileformat or seen_header:
                raise ValueError("vcf_header_invalid")
            columns = line.split("\t")
            if columns[:8] != ["#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO"]:
                raise ValueError("vcf_columns_invalid")
            if len(columns) > 8 and columns[8] != "FORMAT":
                raise ValueError("vcf_format_invalid")
            sample_count = max(0, len(columns) - 9)
            if sample_count > 1000:
                raise ValueError("vcf_too_many_samples")
            seen_header = True
        elif line.startswith("#"):
            if seen_header:
                raise ValueError("vcf_metadata_after_header")
        else:
            if not seen_header:
                raise ValueError("vcf_missing_header")
            columns = line.split("\t")
            if len(columns) != 9 + sample_count if sample_count else len(columns) != 8 and len(columns) != 9:
                raise ValueError("vcf_record_columns_invalid")
            if not columns[0] or not columns[1].isdigit() or int(columns[1]) < 1:
                raise ValueError("vcf_position_invalid")
            if not columns[3] or not columns[4]:
                raise ValueError("vcf_alleles_invalid")
            variant_count += 1
            if variant_count > MAX_VARIANTS:
                raise ValueError("vcf_variant_limit")
    if not seen_header:
        raise ValueError("vcf_missing_header")
    return VcfPreflight(sha256(data).hexdigest(), reference_build, sample_count, variant_count, len(contigs))
