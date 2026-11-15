"""Limbo Atlas E3: opt-in, local, append-only public research memory.

Receipts are metadata observations, *not* authenticated papers or facts.
This is deliberately separate from KLONE's private Memory Core and is never
exposed as an unauthenticated write endpoint. No network or external posting.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import stat

from .evidence_io import read_bounded, json_object, write_new_report
from .limbo_atlas import BY_SOURCE, MAX_RECORDS, validate_records

MAX_IMPORT = 512
MAX_REPORT_BYTES = 24 * 1024 * 1024
ALLOWED_FIELDS = frozenset(("source_id", "courier_id", "url", "title",
                            "summary", "published_at"))
SCHEMA = 1


def _hash(value) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _memory_path(value: str | Path, *, root: Path | None = None, create: bool = False) -> Path:
    """Reject symlinks, foreign directories and non-regular DB files."""
    base = Path(root or (Path.home() / "klone-var")).expanduser()
    if base.is_symlink():
        raise ValueError("memory root may not be a symlink")
    if create:
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not base.is_dir():
        raise ValueError("memory root missing")
    actual = Path(value).expanduser()
    if actual.parent.resolve() != base.resolve() or actual.name in ("", ".", ".."):
        raise ValueError("memory must be a direct file under the approved root")
    if not actual.name.endswith((".db", ".sqlite3")):
        raise ValueError("memory must use .db or .sqlite3")
    if actual.is_symlink():
        raise ValueError("memory file symlink denied")
    if actual.exists():
        info = actual.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("memory must be a single regular file")
    elif not create:
        raise ValueError("research memory database not found")
    return actual


def _open(path: Path, *, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=15)
    else:
        conn = sqlite3.connect(path, timeout=15)
        os.chmod(path, 0o600)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS atlas_meta(
      name TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS atlas_runs(
      run_id INTEGER PRIMARY KEY AUTOINCREMENT,
      imported_utc TEXT NOT NULL,
      dataset_sha256 TEXT NOT NULL UNIQUE,
      received INTEGER NOT NULL CHECK(received BETWEEN 1 AND 512)
    );
    CREATE TABLE IF NOT EXISTS atlas_articles(
      article_id INTEGER PRIMARY KEY AUTOINCREMENT,
      source_id TEXT NOT NULL,
      url TEXT NOT NULL,
      domain TEXT NOT NULL,
      courier_id INTEGER NOT NULL,
      first_run_id INTEGER NOT NULL REFERENCES atlas_runs(run_id),
      UNIQUE(source_id, url)
    );
    CREATE TABLE IF NOT EXISTS atlas_revisions(
      revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
      article_id INTEGER NOT NULL REFERENCES atlas_articles(article_id),
      version INTEGER NOT NULL,
      record_sha256 TEXT NOT NULL,
      previous_sha256 TEXT,
      title TEXT NOT NULL,
      summary TEXT NOT NULL,
      published_at TEXT,
      first_run_id INTEGER NOT NULL REFERENCES atlas_runs(run_id),
      UNIQUE(article_id, version)
    );
    CREATE TABLE IF NOT EXISTS atlas_run_items(
      run_id INTEGER NOT NULL REFERENCES atlas_runs(run_id),
      article_id INTEGER NOT NULL REFERENCES atlas_articles(article_id),
      revision_id INTEGER NOT NULL REFERENCES atlas_revisions(revision_id),
      status TEXT NOT NULL CHECK(status IN ('new', 'metadata_changed', 'unchanged')),
      PRIMARY KEY(run_id, article_id)
    );
    CREATE INDEX IF NOT EXISTS idx_atlas_runs_recent ON atlas_runs(run_id DESC);
    CREATE INDEX IF NOT EXISTS idx_atlas_revisions_article ON atlas_revisions(article_id, version DESC);
    """)
    row=conn.execute("SELECT value FROM atlas_meta WHERE name='schema_version'").fetchone()
    if row is None:
        conn.execute("INSERT INTO atlas_meta(name,value) VALUES ('schema_version',?)",
                     (str(SCHEMA),))
    elif row["value"] != str(SCHEMA):
        raise ValueError("unsupported Atlas memory schema")


def _normalize(records) -> list[dict]:
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_IMPORT:
        raise ValueError("one to 512 public observations required")
    clean = []
    for i in range(0, len(records), MAX_RECORDS):
        chunk = []
        for row in records[i:i + MAX_RECORDS]:
            if not isinstance(row, dict) or not ALLOWED_FIELDS <= set(row):
                raise ValueError("missing public observation field")
            # Extra computed report fields are never trusted as authority.
            chunk.append({k: row[k] for k in ALLOWED_FIELDS})
        clean.extend(validate_records(chunk))
    seen = set()
    for r in clean:
        key = (r["source_id"], r["url"])
        if key in seen:
            raise ValueError("duplicate publication in one archive batch")
        seen.add(key)
    return sorted(clean, key=lambda r: (r["source_id"], r["url"]))


def _compare(conn: sqlite3.Connection, record: dict, run_id: int) -> dict:
    existing = conn.execute(
        "SELECT article_id FROM atlas_articles WHERE source_id=? AND url=?",
        (record["source_id"], record["url"])
    ).fetchone()
    if existing is None:
        insert = conn.execute(
            "INSERT INTO atlas_articles(source_id,url,domain,courier_id,first_run_id)"
            " VALUES (?,?,?,?,?)",
            (record["source_id"], record["url"], record["domain"],
             record["courier_id"], run_id))
        article_id = insert.lastrowid
        old = None
        status = "new"
    else:
        article_id = existing["article_id"]
        old = conn.execute(
            "SELECT revision_id,version,record_sha256 FROM atlas_revisions "
            "WHERE article_id=? ORDER BY version DESC LIMIT 1", (article_id,)
        ).fetchone()
        status = ("unchanged" if old["record_sha256"] == record["receipt_sha256"]
                  else "metadata_changed")
    if old is None or status == "metadata_changed":
        version = (old["version"] + 1) if old is not None else 1
        version_row = conn.execute(
            "INSERT INTO atlas_revisions(article_id,version,record_sha256,previous_sha256,"
            "title,summary,published_at,first_run_id) VALUES (?,?,?,?,?,?,?,?)",
            (article_id, version, record["receipt_sha256"],
             old["record_sha256"] if old is not None else None,
             record["title"], record["summary"], record["published_at"], run_id))
        revision_id = version_row.lastrowid
    else:
        version = old["version"]
        revision_id = old["revision_id"]
    conn.execute("INSERT INTO atlas_run_items(run_id,article_id,revision_id,status)"
                 " VALUES (?,?,?,?)", (run_id, article_id, revision_id, status))
    return {"source_id":record["source_id"], "domain":record["domain"],
            "courier_id":record["courier_id"], "url":record["url"],
            "title":record["title"], "version":version, "status":status,
            "record_sha256":record["receipt_sha256"],
            "publisher_group":record["publisher_group"],
            "evidence_authenticated":False}


def ingest(db: str | Path, records: list[dict], *,
           root: Path | None = None) -> dict:
    """Atomic append-only import. Replaying identical input does not append a run."""
    observations = _normalize(records)  # fail before DB touches anything
    dest = _memory_path(db, root=root, create=True)
    fingerprint = _hash([r["receipt_sha256"] for r in observations])
    with _open(dest) as conn:
        # sqlite3.executescript() ends an existing transaction implicitly.
        # Initialize the schema first, then acquire the write lock so that all
        # articles, revisions and run memberships are *one atomic import*.
        _initialize(conn)
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        prior = conn.execute(
            "SELECT run_id FROM atlas_runs WHERE dataset_sha256=?", (fingerprint,)
        ).fetchone()
        if prior is not None:
            return {"schema_version":SCHEMA, "kind":"klone-atlas-memory-delta",
                    "status":"already_imported", "run_id":prior["run_id"],
                    "dataset_sha256":fingerprint, "observations":len(observations),
                    "counts":{"new":0,"metadata_changed":0,"unchanged":0},
                    "changes":[], "memory_writes":False,
                    "facts_verified":False,"external_actions":False}
        stamp=datetime.now(timezone.utc).isoformat()
        run_id=conn.execute(
            "INSERT INTO atlas_runs(imported_utc,dataset_sha256,received) VALUES (?,?,?)",
            (stamp,fingerprint,len(observations))
        ).lastrowid
        changes=[_compare(conn,record,run_id) for record in observations]
        counts={key:sum(c["status"] == key for c in changes)
                for key in ("new","metadata_changed","unchanged")}
    return {"schema_version":SCHEMA,"kind":"klone-atlas-memory-delta",
            "status":"archived","run_id":run_id,"imported_utc":stamp,
            "dataset_sha256":fingerprint,"observations":len(observations),
            "counts":counts,"changes":changes,"memory_writes":True,
            "facts_verified":False,"external_actions":False}


def status(db: str | Path, *, root: Path | None = None, limit: int = 50) -> dict:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("invalid history limit")
    dest = _memory_path(db, root=root)
    with _open(dest, readonly=True) as conn:
        version=conn.execute("SELECT value FROM atlas_meta WHERE name='schema_version'").fetchone()
        if version is None or version["value"] != str(SCHEMA):
            raise ValueError("unrecognized Atlas research memory")
        runs=conn.execute("SELECT run_id,imported_utc,dataset_sha256,received FROM atlas_runs "
                          "ORDER BY run_id DESC LIMIT ?", (limit,)).fetchall()
        domain_rows=conn.execute(
            "SELECT a.domain AS domain,COUNT(*) AS unique_articles "
            "FROM atlas_articles a GROUP BY a.domain ORDER BY a.domain"
        ).fetchall()
        changes=conn.execute(
            "SELECT ri.status,a.domain,COUNT(*) AS total FROM atlas_run_items ri "
            "JOIN atlas_articles a ON ri.article_id=a.article_id "
            "GROUP BY ri.status,a.domain ORDER BY a.domain,ri.status"
        ).fetchall()
        stats=conn.execute(
            "SELECT COUNT(*) AS runs FROM atlas_runs"
        ).fetchone()
        articles=conn.execute(
            "SELECT COUNT(*) AS articles FROM atlas_articles"
        ).fetchone()
        revisions=conn.execute(
            "SELECT COUNT(*) AS revisions FROM atlas_revisions"
        ).fetchone()
    return {"schema_version":SCHEMA,"kind":"klone-atlas-memory-status",
            "runs":stats["runs"],"articles":articles["articles"],
            "revisions":revisions["revisions"],"recent_runs":[dict(r) for r in runs],
            "domains":[dict(r) for r in domain_rows],
            "observed_statuses":[dict(r) for r in changes],
            "memory_scope":"standalone_public_research_only",
            "facts_verified":False,"external_actions":False}


def import_report(db: str | Path, report_path: str | Path, *,
                  root: Path | None = None) -> dict:
    raw = read_bounded(Path(report_path).expanduser(), MAX_REPORT_BYTES)
    report = json_object(raw)
    if report.get("kind") != "klone-limbo-atlas-preview":
        raise ValueError("only Atlas E2 public research reports can be archived")
    if report.get("epistemic_status") != "unverified_publisher_reports":
        raise ValueError("report epistemic status invalid")
    return ingest(db, report.get("observations"), root=root)


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    act=parser.add_mutually_exclusive_group(required=True)
    act.add_argument("--ingest",type=Path,help="Import an existing public Atlas E2 JSON")
    act.add_argument("--status",action="store_true",help="Read existing public-memory status")
    parser.add_argument("--db",required=True,type=Path)
    parser.add_argument("--output",type=Path,help="New JSON for the research dashboard; never overwrite")
    args=parser.parse_args(argv)
    try:
        report=(import_report(args.db,args.ingest) if args.ingest else status(args.db))
        if args.output:
            rendered=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
            write_new_report(args.output.expanduser(),rendered,Path.cwd().resolve())
        print(json.dumps({"kind":report["kind"],"status":report.get("status"),
                          "counts":report.get("counts"),
                          "runs":report.get("runs"),"articles":report.get("articles"),
                          "revisions":report.get("revisions"),
                          "output":str(args.output) if args.output else None},
                         ensure_ascii=False))
    except (ValueError, OSError, sqlite3.Error, TypeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
