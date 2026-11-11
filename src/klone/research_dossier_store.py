"""Append-only SQLite storage for canonical public research dossier snapshots.

No authentication boundary. Trusted callers must authorize paths and inputs.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3

from .genomics_hypotheses import EvidenceItem, Hypothesis, evaluate_hypotheses


def _canonical(hypotheses: tuple[Hypothesis, ...],
               evidence: tuple[EvidenceItem, ...]) -> str:
    evaluate_hypotheses(hypotheses, evidence)
    if not hypotheses:
        raise ValueError("Dossier requires hypotheses")
    return json.dumps({
        "hypotheses": [asdict(h) for h in sorted(hypotheses, key=lambda x: x.hypothesis_id)],
        "evidence": [asdict(e) for e in sorted(evidence, key=lambda x: x.evidence_id)],
    }, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class DossierStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _initialize(self, db: sqlite3.Connection) -> None:
        db.execute("""CREATE TABLE IF NOT EXISTS research_dossier_snapshots (
            dossier_id TEXT NOT NULL, version INTEGER NOT NULL,
            canonical_json TEXT NOT NULL, fingerprint TEXT NOT NULL,
            PRIMARY KEY(dossier_id, version))""")

    def append(self, *, dossier_id: str, hypotheses: tuple[Hypothesis, ...],
               evidence: tuple[EvidenceItem, ...]) -> int:
        if not isinstance(dossier_id, str) or not 1 <= len(dossier_id) <= 128 or not dossier_id.strip():
            raise ValueError("Invalid dossier id")
        canonical = _canonical(hypotheses, evidence)
        fingerprint = evaluate_hypotheses(hypotheses, evidence)["fingerprint"]
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            self._initialize(db)
            db.execute("BEGIN IMMEDIATE")
            try:
                version = db.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 FROM research_dossier_snapshots WHERE dossier_id=?",
                    (dossier_id,)).fetchone()[0]
                db.execute("INSERT INTO research_dossier_snapshots VALUES (?,?,?,?)",
                           (dossier_id, version, canonical, fingerprint))
                db.commit()
            except Exception:
                db.rollback()
                raise
        return version

    def read(self, *, dossier_id: str, version: int) -> tuple[tuple[Hypothesis, ...], tuple[EvidenceItem, ...]]:
        if not isinstance(dossier_id, str) or not dossier_id.strip() or type(version) is not int or version < 1:
            raise ValueError("Invalid dossier reference")
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            self._initialize(db)
            row = db.execute(
                "SELECT canonical_json,fingerprint FROM research_dossier_snapshots WHERE dossier_id=? AND version=?",
                (dossier_id, version)).fetchone()
        if row is None:
            raise ValueError("Dossier version not found")
        payload = json.loads(row[0])
        hypotheses = tuple(Hypothesis(**h) for h in payload["hypotheses"])
        evidence = tuple(EvidenceItem(**e) for e in payload["evidence"])
        if (_canonical(hypotheses, evidence) != row[0] or
            evaluate_hypotheses(hypotheses, evidence)["fingerprint"] != row[1]):
            raise ValueError("Dossier integrity failure")
        return hypotheses, evidence
