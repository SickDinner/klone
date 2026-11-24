"""Fail-closed peer credential screening and audited receipt intake (LAB ONLY).

No listener, approval, revoke, activation, publication, credential issuer, or
protected IPC is implemented. A "screened" envelope is ONLY a syntactic/UID
preflight and MUST NOT be treated as an authenticated human authorization.
The audit SQLite database and audit key must be protected by a separate OS UID
in a future service. Termux's same-UID clients are deliberately rejected.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import os
import re
import sqlite3
from typing import Callable

from .approval_owner_boundary_v22 import OwnerIsolationUnavailable, kernel_peer_uid

_DOMAIN = "klone-ingress-v24-lab"
_ACTION = "submit_for_verification"  # not approve/revoke/publish
_KEYS = frozenset(("domain", "action", "request_id", "draft_sha256"))
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_GENESIS = "0" * 64
_MAX_BYTES = 4096


class AdmissionDenied(PermissionError):
    """The request was screened out; not proof of durable denial audit."""


class AuditUnavailable(PermissionError):
    """No screened result can be issued without a durable audit transaction."""


@dataclass(frozen=True)
class ScreenedEnvelope:
    """Preflight passed only. Never a permission, approval or signed identity."""
    request_sha256: str
    peer_uid: int


def _owner_uid() -> int:
    fn = getattr(os, "geteuid", None)
    if not callable(fn):
        raise OwnerIsolationUnavailable("service_uid_unsupported")
    uid = fn()
    if type(uid) is not int or uid < 0:
        raise OwnerIsolationUnavailable("service_uid_unavailable")
    return uid


def _strict_pairs(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("duplicate_key")
        data[key] = value
    return data


def _parse_envelope(raw: bytes) -> dict:
    if type(raw) is not bytes or not 1 <= len(raw) <= _MAX_BYTES:
        raise ValueError("invalid_size")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    except (UnicodeError, ValueError, TypeError, OverflowError) as exc:
        raise ValueError("invalid_json") from exc
    if (type(obj) is not dict or set(obj) != _KEYS or
            obj["domain"] != _DOMAIN or obj["action"] != _ACTION or
            type(obj["request_id"]) is not str or not _HEX32.fullmatch(obj["request_id"]) or
            type(obj["draft_sha256"]) is not str or not _HEX64.fullmatch(obj["draft_sha256"])):
        raise ValueError("invalid_envelope")
    return obj


def _tag(secret: bytes, seq: int, ts: int, uid: int | None,
         digest: str, decision: str, reason: str, previous: str) -> str:
    record = json.dumps(["klone-v24-audit", seq, ts, uid, digest, decision,
                         reason, previous], ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return hmac.new(secret, record, sha256).hexdigest()


class V24AuditLedger:
    """Private owner-side SQLite audit; an external checkpoint remains required."""

    def __init__(self, conn: sqlite3.Connection, *, secret: bytes,
                 clock: Callable[[], int]):
        if (not isinstance(conn, sqlite3.Connection) or conn.isolation_level is not None or
                conn.in_transaction):
            raise ValueError("idle_autocommit_connection_required")
        if type(secret) is not bytes or len(secret) < 32:
            raise ValueError("private_audit_secret_required")
        if not callable(clock):
            raise ValueError("clock_required")
        self.conn, self._secret, self._clock = conn, secret, clock
        # Do not silently initialize an arbitrary shared/production database.
        expected = {"approval_v24_ingress_seen", "approval_v24_ingress_audit"}
        try:
            found = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'approval_v24_ingress_%'")}
        except sqlite3.Error as exc:
            raise AuditUnavailable("audit_schema_unavailable") from exc
        if found != expected:
            raise AuditUnavailable("audit_schema_missing")

    @staticmethod
    def initialize_lab_schema(conn: sqlite3.Connection) -> None:
        """Explicit setup for isolated lab databases ONLY; no production migration."""
        if (not isinstance(conn, sqlite3.Connection) or conn.isolation_level is not None or
                conn.in_transaction):
            raise ValueError("idle_autocommit_connection_required")
        conn.executescript("""
            CREATE TABLE approval_v24_ingress_seen (
                request_id TEXT PRIMARY KEY NOT NULL
            );
            CREATE TABLE approval_v24_ingress_audit (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                observed_at INTEGER NOT NULL,
                peer_uid INTEGER,
                request_sha256 TEXT NOT NULL,
                decision TEXT NOT NULL CHECK(decision IN ('screened','denied')),
                reason TEXT NOT NULL,
                previous_tag TEXT NOT NULL,
                event_tag TEXT NOT NULL
            );
        """)

    def _verify_open_transaction(self) -> tuple[int, str]:
        """Detect modifications against local HMAC chain; no remote anchoring."""
        previous = _GENESIS
        last = 0
        for seq, ts, uid, digest, decision, reason, parent, event in self.conn.execute(
                "SELECT seq,observed_at,peer_uid,request_sha256,decision,reason,"
                "previous_tag,event_tag FROM approval_v24_ingress_audit ORDER BY seq"):
            if (type(seq) is not int or seq != last + 1 or parent != previous or
                    not hmac.compare_digest(event, _tag(self._secret, seq, ts, uid,
                                                        digest, decision, reason, parent))):
                raise AuditUnavailable("audit_chain_inconsistent")
            previous = event
            last = seq
        return last, previous

    def verify_chain(self) -> bool:
        try:
            self._verify_open_transaction()
            return True
        except (AuditUnavailable, sqlite3.Error, TypeError, ValueError):
            return False

    def record(self, *, peer_uid: int | None, request_sha256: str,
               reason: str, request_id: str | None) -> str:
        """Atomically mark replay + audit a denial/screening. Return final decision.

        A failure to commit causes AuditUnavailable and NEVER permits screening.
        Invalid/missing peer, unsupported platform, or malformed request is
        logged without ever storing the raw request payload.
        """
        try:
            ts = self._clock()
            if type(ts) is not int or ts < 0:
                raise ValueError("invalid_clock")
        except (ValueError, TypeError, OverflowError) as exc:
            raise AuditUnavailable("trusted_clock_unavailable") from exc
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                seq, previous = self._verify_open_transaction()
                decision = "denied" if reason else "screened"
                if decision == "screened":
                    if not request_id:
                        raise AuditUnavailable("missing_request_id")
                    try:
                        self.conn.execute(
                            "INSERT INTO approval_v24_ingress_seen(request_id) VALUES (?)",
                            (request_id,),
                        )
                    except sqlite3.IntegrityError:
                        decision, reason = "denied", "replayed_request"
                seq += 1
                event = _tag(self._secret, seq, ts, peer_uid, request_sha256,
                             decision, reason, previous)
                self.conn.execute(
                    "INSERT INTO approval_v24_ingress_audit "
                    "(seq,observed_at,peer_uid,request_sha256,decision,reason,previous_tag,event_tag) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (seq, ts, peer_uid, request_sha256, decision, reason, previous, event),
                )
                self.conn.commit()
                return decision if decision == "screened" else reason
            except BaseException:
                self.conn.rollback()
                raise
        except (sqlite3.Error, AuditUnavailable, TypeError, ValueError, OverflowError) as exc:
            raise AuditUnavailable("audit_write_failed") from exc


def screen_draft_envelope(conn, raw: bytes, *, ledger: V24AuditLedger,
                          allowed_peer_uids: frozenset[int]) -> ScreenedEnvelope:
    """Screen one request from a connected AF_UNIX socket; never execute it.

    A real separate-UID service must own the ledger, signing keys and database.
    No caller-provided actor name or UID is ever accepted as authentication.
    """
    if not isinstance(ledger, V24AuditLedger):
        raise TypeError("trusted_audit_ledger_required")
    if (type(allowed_peer_uids) is not frozenset or not allowed_peer_uids or
            any(type(uid) is not int or uid < 0 for uid in allowed_peer_uids)):
        raise ValueError("trusted_peer_allowlist_required")
    digest = sha256(raw[:_MAX_BYTES] if type(raw) is bytes else b"").hexdigest()
    uid = None
    reason = ""
    envelope = None
    try:
        uid = kernel_peer_uid(conn)
        if uid == _owner_uid():
            raise AdmissionDenied("same_uid_not_isolated")
        if uid not in allowed_peer_uids:
            raise AdmissionDenied("peer_not_allowlisted")
        try:
            envelope = _parse_envelope(raw)
        except ValueError as exc:
            raise AdmissionDenied("invalid_request_envelope") from exc
    except OwnerIsolationUnavailable:
        reason = "kernel_peer_unavailable"
    except AdmissionDenied as exc:
        reason = str(exc)
    # A denial is logged too. Audit failure prevents issuing any result.
    outcome = ledger.record(peer_uid=uid, request_sha256=digest,
                            reason=reason,
                            request_id=envelope["request_id"] if envelope else None)
    if outcome != "screened":
        raise AdmissionDenied(outcome)
    return ScreenedEnvelope(request_sha256=digest, peer_uid=uid)
