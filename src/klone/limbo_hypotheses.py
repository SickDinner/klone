"""Atlas E7: owner-controlled hypothesis journal with versioned source links.

Research-room memories are reference material, not proof. The hypothesis
journal lives in a separate opt-in, local SQLite database. Writes are ONLY
via explicit owner CLI --commit. No HTTP mutations, external communication,
automatic scientific approval or private Memory Core reads.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import stat

from .evidence_io import write_new_report
from .guards import access_guard
from .limbo_atlas import BY_DOMAIN
from .limbo_intelligence import _memories
from .limbo_memory import _memory_path
from .limbo_memory_bridge import ROOM

MAX_NOTES=700
MAX_TITLE=240
MAX_EVENT_LINKS=24
STANCES=("context", "support_candidate", "counter_candidate")
STATES=("proposed","in_review","needs_replication","inconclusive","retired")
SCHEMA=1


def _hash(data) -> str:
    return sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,
            separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()


def _plain(value, *, name, max_len):
    if not isinstance(value,str) or not (1 <= len(value.strip()) <= max_len):
        raise ValueError(name+" requires 1.."+str(max_len)+" chars")
    if any(ord(x)<32 and x not in "\n\t" for x in value) or "\x00" in value:
        raise ValueError(name+" contains control characters")
    return value.strip()


def _open(path: Path,*,readonly=False):
    if readonly:
        conn=sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=15)
    else:
        conn=sqlite3.connect(path,timeout=15)
        path.chmod(0o600)
    conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


@contextmanager
def _db(path:Path,*,readonly=False):
    conn=_open(path,readonly=readonly)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _schema(conn):
    conn.executescript("""
      CREATE TABLE IF NOT EXISTS atlas_hypotheses(
        hypothesis_id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        domain TEXT NOT NULL,
        question TEXT NOT NULL,
        falsifier TEXT NOT NULL,
        created_by TEXT NOT NULL CHECK(created_by='owner'),
        UNIQUE(domain,title,question)
      );
      CREATE TABLE IF NOT EXISTS atlas_hypothesis_events(
        event_id INTEGER PRIMARY KEY,
        hypothesis_id INTEGER NOT NULL REFERENCES atlas_hypotheses(hypothesis_id),
        revision INTEGER NOT NULL CHECK(revision>0),
        event_type TEXT NOT NULL CHECK(event_type IN ('proposed','source_link','review')),
        payload_json TEXT NOT NULL,
        previous_hash TEXT,
        event_hash TEXT NOT NULL UNIQUE,
        UNIQUE(hypothesis_id,revision)
      );
      CREATE TABLE IF NOT EXISTS atlas_hypotheses_meta(
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      );
    """)
    found=conn.execute("SELECT value FROM atlas_hypotheses_meta WHERE key='schema'").fetchone()
    if found is None:
        conn.execute("INSERT INTO atlas_hypotheses_meta(key,value) VALUES ('schema',?)",(str(SCHEMA),))
    elif found["value"] != str(SCHEMA):
        raise ValueError("unsupported E7 journal schema")


def _readonly_schema(conn):
    required={"atlas_hypotheses","atlas_hypothesis_events","atlas_hypotheses_meta"}
    found={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not required<=found:raise ValueError("not an initialized E7 hypothesis journal")
    row=conn.execute("SELECT value FROM atlas_hypotheses_meta WHERE key='schema'").fetchone()
    if row is None or row["value"]!=str(SCHEMA):
        raise ValueError("invalid E7 journal schema")


def _guard():
    if access_guard.evaluate(room_id=ROOM,actor_role="owner",
                             requested_permission="read").decision!="allowed":
        raise PermissionError("owner cannot inspect public research-room")
    if access_guard.evaluate(room_id=ROOM,actor_role="worker",
                             requested_permission="write").decision=="allowed":
        raise PermissionError("unexpected worker research-room write permission")


def _existing(conn,hypothesis_id):
    row=conn.execute("SELECT * FROM atlas_hypotheses WHERE hypothesis_id=?",
                     (hypothesis_id,)).fetchone()
    if row is None:raise ValueError("unknown hypothesis ID")
    return dict(row)


def _history(conn,hypothesis_id):
    _existing(conn,hypothesis_id)
    rows=conn.execute(
        "SELECT revision,event_type,payload_json,previous_hash,event_hash "
        "FROM atlas_hypothesis_events WHERE hypothesis_id=? ORDER BY revision",
        (hypothesis_id,)
    ).fetchall()
    if not rows:raise ValueError("hypothesis has no proposal event")
    previous=None
    items=[]
    for n,row in enumerate(rows,start=1):
        payload=json.loads(row["payload_json"])
        digest=_hash([hypothesis_id,n,row["event_type"],payload,previous])
        if row["revision"]!=n or row["previous_hash"]!=previous or row["event_hash"]!=digest:
            raise ValueError("hypothesis revision/hash chain corrupted")
        if n==1 and row["event_type"]!="proposed":
            raise ValueError("hypothesis must start with a proposal")
        items.append({"revision":n,"event_type":row["event_type"],
                      "payload":payload,"previous_hash":previous,
                      "event_hash":row["event_hash"]})
        previous=digest
    return items


def _append(conn,hid,kind,payload,expected_revision):
    events=_history(conn,hid)
    current=len(events)
    if type(expected_revision) is not int or current!=expected_revision:
        raise ValueError("stale hypothesis revision; reload current history")
    prev=events[-1]["event_hash"]
    revision=current+1
    fingerprint=_hash([hid,revision,kind,payload,prev])
    conn.execute(
        "INSERT INTO atlas_hypothesis_events"
        "(hypothesis_id,revision,event_type,payload_json,previous_hash,event_hash)"
        " VALUES (?,?,?,?,?,?)",
        (hid,revision,kind,json.dumps(payload,ensure_ascii=False,sort_keys=True,
          separators=(",",":"),allow_nan=False),prev,fingerprint)
    )
    return revision


def create(journal_db,core_db,*,title,domain,question,falsifier,
           commit=False,root=None):
    """A falsifiable proposal, not a truth claim. Never needs guessed evidence."""
    _guard()
    title=_plain(title,name="title",max_len=MAX_TITLE)
    question=_plain(question,name="question",max_len=MAX_NOTES)
    falsifier=_plain(falsifier,name="falsifier",max_len=MAX_NOTES)
    if domain not in BY_DOMAIN:raise ValueError("unknown research domain")
    # Ensure the actual core DB is public-room-readable and initialized.
    count=len(_memories(core_db))
    if count==0:raise ValueError("no public research memories to ground hypothesis work")
    payload={"kind":"unverified_research_hypothesis","title":title,"domain":domain,
             "question":question,"falsifier":falsifier,
             "truth_verified":False,"author":"owner","memory_snapshot_count":count}
    if not commit:
        return {"kind":"klone-e7-proposal","mode":"preview",
                "hypothesis":payload,"memory_write":False}
    dest=_memory_path(journal_db,root=root,create=True)
    with _db(dest) as conn:
        _schema(conn)
        conn.commit()  # executescript commits; lock the complete insertion afterwards
        conn.execute("BEGIN IMMEDIATE")
        existing=conn.execute(
            "SELECT hypothesis_id FROM atlas_hypotheses WHERE domain=? AND title=? AND question=?",
            (domain,title,question)).fetchone()
        if existing is not None:
            raise ValueError("hypothesis already exists; use its ID instead")
        hid=conn.execute(
            "INSERT INTO atlas_hypotheses(title,domain,question,falsifier,created_by)"
            " VALUES (?,?,?,?,?)",(title,domain,question,falsifier,"owner")
        ).lastrowid
        fingerprint=_hash([hid,1,"proposed",payload,None])
        conn.execute(
            "INSERT INTO atlas_hypothesis_events"
            "(hypothesis_id,revision,event_type,payload_json,previous_hash,event_hash)"
            " VALUES (?,?,?,?,?,?)",
            (hid,1,"proposed",
             json.dumps(payload,ensure_ascii=False,sort_keys=True,
                        separators=(",",":"),allow_nan=False),None,fingerprint)
        )
    return {"kind":"klone-e7-proposal","mode":"committed","hypothesis_id":hid,
            "revision":1,"event_hash":fingerprint,"memory_write":True,
            "truth_verified":False}


def attach(journal_db,core_db,*,hypothesis_id,source_event_id,stance,
           note,expected_revision,commit=False,root=None):
    """Attach only an actual, CURRENT, public research source event."""
    _guard()
    if type(hypothesis_id) is not int or hypothesis_id<1:
        raise ValueError("invalid hypothesis ID")
    if type(source_event_id) is not int or source_event_id<1:
        raise ValueError("invalid Memory Core event ID")
    if stance not in STANCES:raise ValueError("invalid stance")
    note=_plain(note,name="evidence note",max_len=MAX_NOTES)
    docs=_memories(core_db)
    known={d["event_id"]:d for d in docs}
    source=known.get(source_event_id)
    if source is None:raise ValueError("source is not current public research memory")
    ref={key:source[key] for key in ("event_id","article_id","revision_id","version",
                                    "source_id","source_url","publisher_group",
                                    "receipt_sha256","domain")}
    payload={"stance":stance,"source":ref,"note":note,
             "source_claim_verified":False,"independent_evidence_verified":False,
             "owner_reviewed_source":False}
    dest=_memory_path(journal_db,root=root)
    with _db(dest,readonly=True) as conn:
        _readonly_schema(conn)
        chain=_history(conn,hypothesis_id)
    if type(expected_revision) is not int or len(chain)!=expected_revision:
        raise ValueError("stale hypothesis revision")
    for event in chain:
        if event["event_type"]=="source_link":
            other=event["payload"]["source"]
            if other["event_id"]==source_event_id:
                raise ValueError("source event already attached")
    if sum(e["event_type"]=="source_link" for e in chain)>=MAX_EVENT_LINKS:
        raise ValueError("hypothesis source link limit reached")
    if not commit:
        return {"kind":"klone-e7-source-link","mode":"preview","hypothesis_id":hypothesis_id,
                "next_revision":expected_revision+1,"payload":payload,"memory_write":False}
    with _db(dest) as conn:
        conn.execute("BEGIN IMMEDIATE")
        _readonly_schema(conn)
        # Reject concurrent additions; a source can be linked just once.
        current=_history(conn,hypothesis_id)
        if any(e["event_type"]=="source_link" and
               e["payload"]["source"]["event_id"]==source_event_id for e in current):
            raise ValueError("source event already attached")
        rev=_append(conn,hypothesis_id,"source_link",payload,expected_revision)
    return {"kind":"klone-e7-source-link","mode":"committed",
            "hypothesis_id":hypothesis_id,"revision":rev,
            "memory_write":True,"source_claim_verified":False}


def review(journal_db,*,hypothesis_id,state,notes,expected_revision,
           commit=False,root=None):
    """Owner may triage progress, never certify an unverified paper as truth."""
    _guard()
    if type(hypothesis_id) is not int or hypothesis_id<1:
        raise ValueError("invalid hypothesis ID")
    if state not in STATES:raise ValueError("unsupported review state")
    notes=_plain(notes,name="review notes",max_len=MAX_NOTES)
    dest=_memory_path(journal_db,root=root)
    with _db(dest,readonly=True) as conn:
        _readonly_schema(conn)
        chain=_history(conn,hypothesis_id)
    if type(expected_revision) is not int or len(chain)!=expected_revision:
        raise ValueError("stale hypothesis revision")
    payload={"state":state,"reviewer":"owner","notes":notes,
             "source_claims_verified":False,"scientific_conclusion":None}
    if not commit:
        return {"kind":"klone-e7-review","mode":"preview",
                "hypothesis_id":hypothesis_id,"next_revision":expected_revision+1,
                "payload":payload,"memory_write":False}
    with _db(dest) as conn:
        conn.execute("BEGIN IMMEDIATE")
        _readonly_schema(conn)
        rev=_append(conn,hypothesis_id,"review",payload,expected_revision)
    return {"kind":"klone-e7-review","mode":"committed",
            "hypothesis_id":hypothesis_id,"revision":rev,
            "state":state,"memory_write":True,"scientific_conclusion":None}


def detail(journal_db,hypothesis_id,*,root=None,core_db=None):
    dest=_memory_path(journal_db,root=root)
    with _db(dest,readonly=True) as conn:
        _readonly_schema(conn)
        hypothesis=_existing(conn,hypothesis_id)
        events=_history(conn,hypothesis_id)
    linked=[e["payload"] for e in events if e["event_type"]=="source_link"]
    state=next((e["payload"]["state"] for e in reversed(events)
                if e["event_type"]=="review"),"proposed")
    counts=dict(sorted(Counter(e["stance"] for e in linked).items()))
    publishers=sorted({x["source"]["publisher_group"] for x in linked})
    stale=[]
    if core_db is not None and linked:
        known={d["event_id"]:d for d in _memories(core_db)}
        for link in linked:
            origin=link["source"]
            doc=known.get(origin["event_id"])
            if doc is None or doc["receipt_sha256"]!=origin["receipt_sha256"]:
                stale.append(origin["event_id"])
    checks={
        "open_original_sources":len(linked),
        "inspect_study_designs":len(linked),
        "find_counterevidence":int(not counts.get("counter_candidate")),
        "independent_replication_not_demonstrated":True,
        "claims_verified":False,
    }
    return {
        "kind":"klone-e7-hypothesis-history","schema_version":SCHEMA,
        "hypothesis":hypothesis,"revision":len(events),"state":state,
        "events":events,"linked_sources":len(linked),
        "publisher_groups":publishers,"publisher_groups_not_independent_sources":True,
        "stance_counts":counts,"stale_source_event_ids":stale,
        "evidence_debt":checks,"scientifically_verified":False,
        "read_only":True,
    }


def list_hypotheses(journal_db,*,root=None,limit=100):
    if type(limit) is not int or not 1<=limit<=100:
        raise ValueError("limit must be 1..100")
    dest=_memory_path(journal_db,root=root)
    with _db(dest,readonly=True) as conn:
        _readonly_schema(conn)
        rows=conn.execute("SELECT hypothesis_id FROM atlas_hypotheses "
                          "ORDER BY hypothesis_id DESC LIMIT ?",(limit,)).fetchall()
    return {"kind":"klone-e7-hypothesis-list",
            "hypotheses":[detail(journal_db,int(row["hypothesis_id"]),root=root)
                          for row in rows],
            "memory_write":False}


def main(argv=None):
    p=argparse.ArgumentParser(description="KLONE E7 public research hypothesis journal (owner CLI only)")
    p.add_argument("--journal-db",type=Path,default=Path.home()/"klone-var"/"atlas-hypotheses.sqlite3")
    p.add_argument("--klone-db",type=Path)
    action=p.add_mutually_exclusive_group(required=True)
    action.add_argument("--propose",action="store_true")
    action.add_argument("--attach",action="store_true")
    action.add_argument("--review",action="store_true")
    action.add_argument("--detail",action="store_true")
    action.add_argument("--list",action="store_true")
    p.add_argument("--commit",action="store_true",help="Explicit owner-controlled journal write")
    p.add_argument("--hypothesis-id",type=int)
    p.add_argument("--expected-revision",type=int)
    p.add_argument("--title")
    p.add_argument("--domain")
    p.add_argument("--question")
    p.add_argument("--falsifier")
    p.add_argument("--source-event-id",type=int)
    p.add_argument("--stance",choices=STANCES)
    p.add_argument("--note")
    p.add_argument("--state",choices=STATES)
    p.add_argument("--output",type=Path)
    args=p.parse_args(argv)
    if args.commit and (args.detail or args.list):
        p.error("read-only actions cannot use --commit")
    try:
        if args.propose:
            if not args.klone_db:p.error("--klone-db required for proposal")
            result=create(args.journal_db,args.klone_db,
                 title=args.title,domain=args.domain,question=args.question,
                 falsifier=args.falsifier,commit=args.commit)
        elif args.attach:
            if not args.klone_db:p.error("--klone-db required for linking")
            result=attach(args.journal_db,args.klone_db,
                 hypothesis_id=args.hypothesis_id,source_event_id=args.source_event_id,
                 stance=args.stance,note=args.note,
                 expected_revision=args.expected_revision,commit=args.commit)
        elif args.review:
            result=review(args.journal_db,hypothesis_id=args.hypothesis_id,
                          state=args.state,notes=args.note,
                          expected_revision=args.expected_revision,commit=args.commit)
        elif args.detail:
            if args.hypothesis_id is None:p.error("--hypothesis-id required")
            result=detail(args.journal_db,args.hypothesis_id,core_db=args.klone_db)
        else:result=list_hypotheses(args.journal_db)
        if args.output:
            write_new_report(args.output.expanduser(),
                json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
                Path.cwd().resolve())
        print(json.dumps({k:v for k,v in result.items()
                          if k in ("kind","mode","hypothesis_id","revision",
                                   "state","linked_sources","memory_write")},
                         ensure_ascii=False))
    except (ValueError,PermissionError,sqlite3.Error,OSError,TypeError) as exc:
        p.error(str(exc))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
