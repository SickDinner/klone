"""Strict, bounded import of explicitly provided public research dossier JSON.

No file-system traversal, URLs, private data discovery or remote fetching.
"""
from __future__ import annotations

import json

from .genomics_hypotheses import EvidenceItem, Hypothesis
from .research_dossier import ResearchDossier, build_dossier


def import_public_dossier_json(data: str, *, version: int = 1) -> ResearchDossier:
    if not isinstance(data, str) or len(data.encode("utf-8")) > 1_000_000:
        raise ValueError("Dossier JSON exceeds size limit")
    try:
        obj = json.loads(data)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid dossier JSON") from exc
    if not isinstance(obj, dict) or set(obj) != {"hypotheses", "evidence"}:
        raise ValueError("Expected hypotheses and evidence fields")
    if not isinstance(obj["hypotheses"], list) or not isinstance(obj["evidence"], list):
        raise ValueError("Expected arrays")
    if len(obj["hypotheses"]) > 100 or len(obj["evidence"]) > 5000:
        raise ValueError("Dossier item count exceeds limit")
    hypotheses = []
    for row in obj["hypotheses"]:
        if not isinstance(row, dict) or set(row) != {"hypothesis_id", "statement"}:
            raise ValueError("Invalid hypothesis fields")
        hypotheses.append(Hypothesis(**row))
    evidence = []
    expected = set(EvidenceItem.__dataclass_fields__)
    for row in obj["evidence"]:
        if not isinstance(row, dict) or set(row) != expected:
            raise ValueError("Invalid evidence fields")
        evidence.append(EvidenceItem(**row))
    return build_dossier(version=version, hypotheses=tuple(hypotheses),
                         evidence=tuple(evidence))
