"""Atlas E5: explicit owner bridge from E3 public research to KLONE Memory Core.

Only validated *public publisher metadata* is imported as unverified,
provenance-linked memory events in the dedicated research-room. This module
does not copy into personal, sealed or genomics rooms, impersonate users,
run web requests, or silently approve scientific claims.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import stat

from .audit import AuditService
from .evidence_io import checked_path, write_new_report
from .guards import access_guard, classification_guard
from .limbo_memory import _memory_path
from .limbo_queue import _latest_public
from .memory import MemoryService
from .repository import KloneRepository, utc_now_iso
from .rooms import room_registry

ROOM = "research-room"
CLASSIFICATION = "public"
SOURCE_TABLE = "atlas_revisions"
EVENT_TYPE = "unverified_public_research_observation"
MAX_IMPORT = 512
MAX_SEARCH = 10000


def _target(path: str | Path, source: Path) -> Path:
    value = checked_path(Path(path).expanduser())
    if not value.exists():
        raise ValueError("target KLONE Memory Core database must already exist")
    info = value.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("target KLONE database must be a regular single file")
    if value.resolve() == source.resolve():
        raise ValueError("source E3 SQLite and target KLONE DB must differ")
    return value


def _schema(conn: sqlite3.Connection) -> None:
    expected = {"memory_events", "memory_provenance", "audit_events"}
    actual = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not expected <= actual:
        raise ValueError("target is not an initialized KLONE Memory Core database")


def _guard_owner() -> None:
    room = room_registry.get_room(ROOM)
    if room is None or room.classification != CLASSIFICATION or room.status != "active":
        raise PermissionError("public research-room policy unavailable")
    if access_guard.evaluate(room_id=ROOM, actor_role="owner",
                             requested_permission="write").decision != "allowed":
        raise PermissionError("owner write permission to research-room denied")
    if classification_guard.evaluate(room_id=ROOM,
                                     classification_level=CLASSIFICATION).decision != "allowed":
        raise PermissionError("research-room public classification denied")
    if access_guard.evaluate(room_id="public-room", actor_role="owner",
                             requested_permission="write").decision == "allowed":
        raise PermissionError("original public-room write boundary changed unexpectedly")


def _record_key(doc: dict) -> str:
    return "article:" + str(doc["article_id"]) + ":revision:" + str(doc["revision_id"])


def _payload(doc: dict, recorded_at: str) -> dict:
    return {
        "room_id": ROOM,
        "classification_level": CLASSIFICATION,
        "event_type": EVENT_TYPE,
        "source_table": SOURCE_TABLE,
        "source_record_id": _record_key(doc),
        # Publisher time is metadata, not the time KLONE established a fact.
        "occurred_at": recorded_at,
        "recorded_at": recorded_at,
        "title": "Julkinen lähdehavainto (vahvistamaton): " + doc["title"][:240],
        "evidence_text": (
            "VAHVISTAMATON JULKINEN LÄHDEHAVAINTO, EI VARMENNETTU TOSIASIA\n"
            "Julkaisun otsikko: " + doc["title"] + "\n"
            "Lähteen kuvaus: " + doc["summary"] + "\n"
            "Alkuperäinen julkaisu: " + doc["url"] + "\n"
            "Tarkista alkuperäisjulkaisu ja mahdollinen vertaisarviointi."
        ),
        "metadata": {
            "epistemic_status": "unverified_publisher_claim",
            "knowledge_type": "research_metadata",
            "source_url": doc["url"],
            "source_id": doc["source_id"],
            "publisher_group": doc["publisher_group"],
            "domain": doc["domain"],
            "courier_id": doc["courier_id"],
            "article_id": doc["article_id"],
            "revision_id": doc["revision_id"],
            "version": doc["version"],
            "published_at": doc["published_at"],
            "source_receipt_sha256": doc["receipt_sha256"],
            "private_room_join": False,
            "truth_verified": False,
        },
    }


def _selected(source_db, *, root, offset, limit):
    if type(limit) is not int or not 1 <= limit <= MAX_IMPORT:
        raise ValueError("limit must be an integer 1..512")
    if type(offset) is not int or not 0 <= offset <= 100000:
        raise ValueError("offset out of range")
    docs = sorted(_latest_public(source_db, root=root), key=lambda d:d["article_id"])
    return docs[offset:offset+limit], len(docs)


def bridge(source_db: str | Path, klone_db: str | Path, *,
           commit: bool = False, offset: int = 0,
           limit: int = MAX_IMPORT, root: Path | None = None) -> dict:
    """Preview by default. --commit executes guarded, transactional owner import."""
    if type(commit) is not bool:
        raise ValueError("commit must be boolean")
    _guard_owner()
    src = _memory_path(source_db, root=root)
    target = _target(klone_db, src)
    docs, total = _selected(src, root=root, offset=offset, limit=limit)
    if not docs:
        raise ValueError("selected research range is empty")
    stamp = utc_now_iso()
    service = KloneRepository(target)
    keys = [(d, _record_key(d)) for d in docs]
    ids = []
    inserted = []
    with (service.connection() if commit else
          closing(sqlite3.connect(target.as_uri()+"?mode=ro", uri=True, timeout=15))) as conn:
        _schema(conn)
        existing = {}
        for doc, key in keys:
            row = conn.execute(
                "SELECT id,metadata_json FROM memory_events WHERE room_id=? "
                "AND source_table=? AND source_record_id=? AND event_type=?",
                (ROOM, SOURCE_TABLE, key, EVENT_TYPE)).fetchone()
            if row:
                # Never silently accept an old event whose provenance differs
                # from the current E3 snapshot.
                identifier, metadata_json = row
                meta = json.loads(metadata_json) if metadata_json else {}
                if meta.get("source_receipt_sha256") != doc["receipt_sha256"]:
                    raise ValueError("existing Memory Core event has conflicting source receipt")
                existing[key] = int(identifier)
        if commit:
            audit = AuditService(service)
            for doc, key in keys:
                if key in existing:
                    ids.append(existing[key])
                    continue
                payload = _payload(doc, stamp)
                row, created = service.upsert_memory_event(payload, conn=conn)
                if not created:
                    raise ValueError("unexpected duplicate Memory Core source event")
                event_id = int(row["id"])
                _, linked = service.upsert_memory_provenance({
                    "room_id": ROOM,
                    "owner_type": "event",
                    "owner_id": str(event_id),
                    "provenance_type": "source_lineage",
                    "source_table": SOURCE_TABLE,
                    "source_record_id": str(doc["revision_id"]),
                    "source_field": "url",
                    "basis_type": "source_receipt_sha256",
                    "basis_value": doc["receipt_sha256"],
                }, conn=conn)
                if not linked:
                    raise ValueError("missing new provenance for research memory event")
                ids.append(event_id)
                inserted.append(event_id)
            if inserted:
                audit.log_event(
                    event_type="atlas_public_memory_import",
                    actor="owner",
                    target_type="research_memory_batch",
                    target_id="atlas:" + sha256(
                        "|".join(d["receipt_sha256"] for d in docs).encode()).hexdigest()[:24],
                    room_id=ROOM,
                    classification_level=CLASSIFICATION,
                    summary="Owner imported public source metadata as unverified research memories",
                    metadata={
                        "inserted":len(inserted),
                        "already_present":len(existing),
                        "selected_count":len(docs),
                        "source_db_scope":"standalone_atlas_e3",
                        "knowledge_status":"unverified_publisher_claim",
                    },
                    conn=conn,
                )
        else:
            ids = [existing.get(key) for _,key in keys]
    return {
        "kind":"klone-atlas-e5-memory-bridge",
        "schema_version":1,
        "mode":"committed" if commit else "preview",
        "room_id":ROOM,
        "classification_level":CLASSIFICATION,
        "archive_articles":total,
        "selected":len(docs),
        "offset":offset,
        "next_offset":offset+len(docs) if offset+len(docs)<total else None,
        "already_present":len(existing),
        "new_events":len(inserted) if commit else len(docs)-len(existing),
        "inserted_event_ids":inserted,
        "memory_event_ids":ids if commit else [],
        "domains":dict(sorted(Counter(d["domain"] for d in docs).items())),
        "epistemic_status":"unverified_publisher_claim",
        "authorship":"owner_explicit_cli",
        "public_metadata_only":True,
        "memory_events_were_written":bool(inserted),
        "external_network_actions":False,
        "private_memory_access":False,
    }


def recall(klone_db: str | Path, query: str, *, limit: int = 12) -> dict:
    """Read-only citation search from actual KLONE Memory Core research-room."""
    if not isinstance(query,str) or not query.strip() or len(query)>160:
        raise ValueError("search query must have 1..160 characters")
    if type(limit) is not int or not 1<=limit<=30:
        raise ValueError("recall limit must be 1..30")
    path = checked_path(Path(klone_db).expanduser())
    if not path.is_file():
        raise ValueError("Memory Core DB not found")
    if access_guard.evaluate(room_id=ROOM,actor_role="owner",
                             requested_permission="read").decision!="allowed":
        raise PermissionError("research memory room read denied")
    terms = re.findall(r"[\w-]{2,}",query.lower(), flags=re.UNICODE)
    if not terms:
        raise ValueError("query must contain letters or digits")
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=15)) as conn:
        _schema(conn)
        rows = conn.execute(
            "SELECT id,title,metadata_json FROM memory_events "
            "WHERE room_id=? AND event_type=? AND status='active' "
            "ORDER BY id DESC LIMIT ?", (ROOM,EVENT_TYPE,MAX_SEARCH+1)).fetchall()
    if len(rows)>MAX_SEARCH:
        raise ValueError("research-room too large for local search")
    ranked=[]
    for event_id,title,metadata in rows:
        data=json.loads(metadata) if metadata else {}
        if data.get("epistemic_status")!="unverified_publisher_claim":
            continue
        haystack=(str(title)+" "+str(data.get("domain",""))+" "+str(data.get("source_id",""))).lower()
        score=sum(3 if term in haystack else 0 for term in terms)
        if score>0:
            ranked.append({
                "event_id":int(event_id),
                "title":title,
                "domain":data.get("domain"),
                "source_url":data.get("source_url"),
                "source_id":data.get("source_id"),
                "courier_id":data.get("courier_id"),
                "article_id":data.get("article_id"),
                "revision_id":data.get("revision_id"),
                "version":data.get("version"),
                "epistemic_status":"unverified_publisher_claim",
                "score":score,
                "memory_context_url":"/api/memory/context/payload?room_id=research-room&event_id="+str(event_id),
            })
    ranked.sort(key=lambda row:(-row["score"],-row["version"],row["event_id"]))
    return {"kind":"klone-atlas-e5-recall","query":query,
            "room_id":ROOM,"total_matches":len(ranked),"results":ranked[:limit],
            "source_claims_verified":False, "read_only":True}


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--klone-db",type=Path,required=True,
                        help="Existing KLONE Memory Core DB, e.g. ~/klone-var/arxiv-e1.db")
    parser.add_argument("--atlas-db",type=Path,
                        default=Path.home()/"klone-var"/"atlas-memory.sqlite3")
    group=parser.add_mutually_exclusive_group()
    group.add_argument("--commit",action="store_true",help="Explicit owner authorization to write public memories")
    group.add_argument("--recall",type=str,help="Search existing research-room memories without writes")
    parser.add_argument("--offset",type=int,default=0)
    parser.add_argument("--limit",type=int,default=512)
    parser.add_argument("--output",type=Path,help="Optional fresh JSON export outside code tree")
    args=parser.parse_args(argv)
    if args.recall is not None:
        if args.offset!=0 or args.limit!=512:
            parser.error("recall does not accept import offset/limit")
        result=recall(args.klone_db,args.recall)
    else:
        result=bridge(args.atlas_db,args.klone_db,commit=args.commit,
                      offset=args.offset,limit=args.limit)
    if args.output:
        write_new_report(args.output,result_as_json(result),Path.cwd().resolve())
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    return 0


def result_as_json(data: dict) -> str:
    return json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n"


if __name__=="__main__":
    raise SystemExit(main())
