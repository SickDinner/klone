"""Authoritative SQLite publication policy, co-located with claims.

Administrative policy writes MUST be authenticated by the hosting service.
The transaction guard is fail-closed and reads policy under the same SQLite
BEGIN IMMEDIATE transaction as claim and audit writes.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3


def initialize_publication_policy(database_path: Path) -> None:
    with closing(sqlite3.connect(database_path, timeout=10)) as db:
        with db:
            db.execute("""CREATE TABLE IF NOT EXISTS research_publication_policy (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                version INTEGER NOT NULL CHECK(version>0),
                enabled INTEGER NOT NULL CHECK(enabled IN (0,1)))""")
            db.execute("""CREATE TABLE IF NOT EXISTS research_publication_members (
                principal TEXT PRIMARY KEY,
                can_commit INTEGER NOT NULL CHECK(can_commit IN (0,1)))""")
            db.execute("INSERT OR IGNORE INTO research_publication_policy VALUES (1,1,0)")


def set_publication_policy(
    database_path: Path, *, version: int, enabled: bool,
    members: dict[str, bool],
) -> None:
    """Trusted administrator only; monotonic policy version, deny by default."""
    if type(version) is not int or version < 1 or type(enabled) is not bool:
        raise ValueError("Invalid policy revision")
    if not isinstance(members, dict) or len(members) > 10000 or any(
        not isinstance(p, str) or not p.strip() or len(p) > 128
        or type(v) is not bool for p, v in members.items()
    ):
        raise ValueError("Invalid policy members")
    initialize_publication_policy(database_path)
    with closing(sqlite3.connect(database_path, timeout=10)) as db:
        with db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT version FROM research_publication_policy WHERE singleton=1"
            ).fetchone()[0]
            if version <= previous:
                raise ValueError("Policy version must increase")
            db.execute(
                "UPDATE research_publication_policy SET version=?,enabled=? WHERE singleton=1",
                (version, int(enabled)))
            db.execute("DELETE FROM research_publication_members")
            db.executemany(
                "INSERT INTO research_publication_members VALUES (?,?)",
                [(principal, int(allowed)) for principal, allowed in members.items()])


def enforce_publication_policy(
    db: sqlite3.Connection, principal: str, claim_id: str, policy_version: int,
) -> None:
    """Use only inside a caller-owned SQLite write transaction."""
    if (not isinstance(db, sqlite3.Connection)
            or not isinstance(principal, str) or not principal.strip()
            or not isinstance(claim_id, str) or not claim_id.strip()
            or type(policy_version) is not int):
        raise PermissionError("Invalid publication authorization")
    try:
        row = db.execute(
            "SELECT version,enabled FROM research_publication_policy WHERE singleton=1"
        ).fetchone()
        member = db.execute(
            "SELECT can_commit FROM research_publication_members WHERE principal=?",
            (principal,)).fetchone()
    except sqlite3.OperationalError as exc:
        raise PermissionError("Publication policy not initialized") from exc
    if (row is None or row != (policy_version, 1)
            or member != (1,)):
        raise PermissionError("Publication policy denied or revoked")
