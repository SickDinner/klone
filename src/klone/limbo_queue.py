"""Limbo Atlas E4: deterministic, no-network multi-batch Council72 research queue.

Reads the latest public article metadata from the separate E3 SQLite archive.
Produces every citation in balanced, bounded, replayable 48-item batches.
The manifest is a *proposal*, not evidence of specialist review or execution.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from .evidence_io import write_new_report
from .limbo_atlas import BY_DOMAIN, BY_SOURCE, DOMAINS, MAX_RECORDS, plan, validate_records
from .limbo_memory import _connection, _memory_path, SCHEMA

MAX_BATCH = MAX_RECORDS
MAX_ARTICLES = 100000


def _digest(obj) -> str:
    return sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                             allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _latest_public(db: str | Path, *, root: Path | None = None) -> list[dict]:
    """Read a consistent E3 snapshot; don't change the E3 archive."""
    target = _memory_path(db, root=root)
    with _connection(target, readonly=True) as conn:
        v = conn.execute("SELECT value FROM atlas_meta WHERE name='schema_version'").fetchone()
        if v is None or v["value"] != str(SCHEMA):
            raise ValueError("Atlas E3 memory schema not recognized")
        rows = conn.execute("""
            SELECT a.article_id, a.source_id, a.courier_id, a.domain, a.url,
                   r.revision_id, r.version, r.record_sha256,
                   r.title, r.summary, r.published_at
              FROM atlas_articles a
              JOIN atlas_revisions r ON r.article_id=a.article_id
             WHERE r.version=(SELECT MAX(v.version)
                                FROM atlas_revisions v
                               WHERE v.article_id=a.article_id)
          ORDER BY a.article_id
        """).fetchmany(MAX_ARTICLES + 1)
    if len(rows) > MAX_ARTICLES:
        raise ValueError("archive too large for one E4 snapshot")
    if not rows:
        raise ValueError("Atlas E3 has no public articles to review")
    documents = []
    for row in rows:
        o = dict(row)
        spec = BY_SOURCE.get(o["source_id"])
        if spec is None or spec.domain != o["domain"] or (
                BY_DOMAIN[spec.domain].courier != o["courier_id"]):
            raise ValueError("archived source or courier mismatch")
        # No authority fields from the archive are trusted.
        record = {k:o[k] for k in ("source_id","courier_id","url",
                                  "title","summary","published_at")}
        norm = validate_records([record])[0]
        if norm["receipt_sha256"] != o["record_sha256"]:
            raise ValueError("archived receipt does not match source metadata")
        documents.append({**record,"article_id":o["article_id"],
                          "revision_id":o["revision_id"],"version":o["version"],
                          "receipt_sha256":norm["receipt_sha256"],
                          "domain":norm["domain"],
                          "publisher_group":norm["publisher_group"]})
    return documents


def _balanced(records: list[dict]) -> list[dict]:
    """Cycle fields and source IDs, never discarding any saved source record."""
    pools = {d.id:{} for d in DOMAINS}
    for r in records:
        pools[r["domain"]].setdefault(r["source_id"], []).append(r)
    for domain in DOMAINS:
        for items in pools[domain.id].values():
            items.sort(key=lambda r:(r["url"], r["article_id"]))
    ordered = {}
    for domain in DOMAINS:
        p = pools[domain.id]
        result = []
        while any(p.values()):
            for sid in sorted(p):
                if p[sid]:
                    result.append(p[sid].pop(0))
        ordered[domain.id] = result
    result = []
    while any(ordered.values()):
        for domain in DOMAINS:
            if ordered[domain.id]:
                result.append(ordered[domain.id].pop(0))
    if len(result) != len(records) or len({x["article_id"] for x in result}) != len(records):
        raise ValueError("Atlas queue lost or duplicated source articles")
    return result


def manifest(db: str | Path, *, root: Path | None = None,
             batch_size: int = MAX_BATCH) -> dict:
    """Pure read; includes the batch contents so the existing UI can plan each."""
    if type(batch_size) is not int or not 1 <= batch_size <= MAX_BATCH:
        raise ValueError("batch size must be an integer 1..48")
    documents = _balanced(_latest_public(db, root=root))
    digest = _digest([(d["article_id"], d["revision_id"], d["receipt_sha256"])
                      for d in sorted(documents, key=lambda item:item["article_id"])])
    batches = []
    for start in range(0, len(documents), batch_size):
        chunk = documents[start:start + batch_size]
        observations = [
            {k:r[k] for k in ("source_id","courier_id","url","title",
                              "summary","published_at")}
            for r in chunk
        ]
        batch_no = len(batches) + 1
        batches.append({
            "number": batch_no,
            "batch_id": "e4:" + digest[:16] + ":" + str(batch_no),
            "size": len(chunk),
            "domains": dict(sorted(Counter(r["domain"] for r in chunk).items())),
            "publisher_groups": sorted({r["publisher_group"] for r in chunk}),
            "article_ids": [r["article_id"] for r in chunk],
            "receipt_sha256": _digest([(r["article_id"],r["receipt_sha256"]) for r in chunk]),
            "observations": observations,
            "state": "unreviewed_queue_draft",
        })
    return {
        "kind":"klone-atlas-e4-queue",
        "schema_version":1,
        "snapshot_sha256":digest,
        "article_count":len(documents),
        "batch_size":batch_size,
        "batch_count":len(batches),
        "domains":dict(sorted(Counter(d["domain"] for d in documents).items())),
        "batches":batches,
        "authority":{
            "write_e3_memory":False,
            "private_memory_access":False,
            "automatic_research_execution":False,
            "external_actions":False,
            "human_review_required":True,
        },
        "facts_verified":False,
    }


def plan_batch(data: dict, number: int, *,
               target_ring: int | None = None,
               question: str | None = None) -> dict:
    """Plan precisely one queued batch with the existing 72-seat machinery."""
    if not isinstance(data,dict) or data.get("kind") != "klone-atlas-e4-queue":
        raise ValueError("not an Atlas E4 queue manifest")
    batches=data.get("batches")
    if not isinstance(batches,list) or not batches:
        raise ValueError("no E4 batches available")
    if type(number) is not int or not 1 <= number <= len(batches):
        raise ValueError("batch number out of range")
    selected=batches[number-1]
    if type(selected.get("number")) is not int or selected["number"] != number:
        raise ValueError("queue order invalid")
    docs=selected["observations"]
    if not isinstance(docs,list) or len(docs)!=selected.get("size"):
        raise ValueError("batch document count mismatch")
    validate_records(docs)
    result=plan(docs,ring_id=target_ring,question=question)
    return {
        "kind":"klone-atlas-e4-council-draft",
        "schema_version":1,
        "snapshot_sha256":data["snapshot_sha256"],
        "batch_id":selected["batch_id"],
        "batch_number":number,
        "batch_count":len(batches),
        "size":len(docs),
        "review_status":"not_reviewed",
        "council":result,
        "authority":{"external_actions":False,
                     "automatic_approval":False,"memory_write":False},
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description="Offline, all-article E4 queue from E3 public archive")
    parser.add_argument("--db",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path,
                        help="Fresh JSON export, never replace an earlier report")
    parser.add_argument("--batch",type=int,help="Export Council72 draft for this 1-based batch")
    parser.add_argument("--batch-size",type=int,default=MAX_BATCH)
    parser.add_argument("--ring",type=int,help="Optional target specialist ring 2..8")
    parser.add_argument("--question",type=str,help="Optional research question")
    args=parser.parse_args(argv)
    if args.batch is None and (args.ring is not None or args.question is not None):
        parser.error("--ring / --question require --batch")
    report=manifest(args.db,batch_size=args.batch_size)
    if args.batch is not None:
        report=plan_batch(report,args.batch,target_ring=args.ring,question=args.question)
    content=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    write_new_report(args.output.expanduser(),content,Path.cwd().resolve())
    print(json.dumps({
        "kind":report["kind"],"output":str(args.output),
        "batch_count":report.get("batch_count"),
        "article_count":report.get("article_count"),
        "batch_number":report.get("batch_number"),
        "size":report.get("size"),
        "snapshot_sha256":report["snapshot_sha256"]},
        ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
