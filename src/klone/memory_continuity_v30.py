"""Memory Continuity v3.0: public metadata-only snapshot drift checker (LAB).

Uses existing memory_events correction fields; DOES NOT migrate, update, read
protected data, authenticate database provenance or approve any operation.
Only public-room input is accepted. A local digest is NOT an external anchor.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import re

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAX_ROWS = 512
_STATES = frozenset({"active", "rejected", "superseded"})


def _clock(value: str | None, *, required: bool) -> str | None:
    if value is None and not required:
        return None
    if type(value) is not str or len(value) > 40:
        raise ValueError("invalid_memory_time")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_memory_time") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timezone_required")
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


@dataclass(frozen=True)
class PublicMemoryEvent:
    event_id: int
    recorded_at: str
    occurred_at: str
    status: str = "active"
    corrected_at: str | None = None
    superseded_by_id: int | None = None
    correction_reason: str | None = None
    corrected_by_role: str | None = None
    room_id: str = "public-room"
    classification_level: str = "public"

    def __post_init__(self) -> None:
        if type(self.event_id) is not int or not 1 <= self.event_id <= 2**63 - 1:
            raise ValueError("invalid_memory_event_id")
        if self.room_id != "public-room" or self.classification_level != "public":
            raise ValueError("nonpublic_memory_requires_room_scoped_verifier")
        if type(self.status) is not str or self.status not in _STATES:
            raise ValueError("invalid_memory_status")
        recorded = _clock(self.recorded_at, required=True)
        occurred = _clock(self.occurred_at, required=True)
        corrected = _clock(self.corrected_at, required=False)
        if self.status == "active":
            if any(v is not None for v in (
                corrected, self.superseded_by_id, self.correction_reason,
                self.corrected_by_role,
            )):
                raise ValueError("active_memory_has_correction_metadata")
        else:
            if corrected is None or corrected < recorded:
                raise ValueError("correction_before_recording_or_missing")
            if (type(self.correction_reason) is not str or
                    not 1 <= len(self.correction_reason.strip()) <= 160 or
                    type(self.corrected_by_role) is not str or
                    not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", self.corrected_by_role)):
                raise ValueError("incomplete_correction_metadata")
            if self.status == "rejected" and self.superseded_by_id is not None:
                raise ValueError("rejected_memory_cannot_supersede")
            if self.status == "superseded" and (
                type(self.superseded_by_id) is not int or
                self.superseded_by_id <= 0 or
                self.superseded_by_id == self.event_id
            ):
                raise ValueError("invalid_replacement_event")
        object.__setattr__(self, "recorded_at", recorded)
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "corrected_at", corrected)


def project_public_memory_events(rows: Sequence[Mapping]) -> tuple[PublicMemoryEvent, ...]:
    """Project already-authorized MemoryService.query_events output.

    Never fetch a room on behalf of a caller; never copies evidence_text.
    Caller MUST independently authenticate the source snapshot and ensure it
    was gathered consistently, not by racing across multiple DB reads.
    """
    if (not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or
            not 1 <= len(rows) <= _MAX_ROWS):
        raise ValueError("invalid_memory_rows")
    result = []
    required = {"id", "room_id", "classification_level", "status",
                "recorded_at", "occurred_at"}
    for row in rows:
        if not isinstance(row, Mapping) or not required.issubset(row):
            raise ValueError("missing_memory_metadata")
        obj = PublicMemoryEvent(
            event_id=row["id"], room_id=row["room_id"],
            classification_level=row["classification_level"],
            status=row["status"], occurred_at=row["occurred_at"],
            recorded_at=row["recorded_at"],
            corrected_at=row.get("corrected_at"),
            superseded_by_id=row.get("superseded_by_id"),
            correction_reason=row.get("correction_reason"),
            corrected_by_role=row.get("corrected_by_role"),
        )
        if "corrected" in row and (
                type(row["corrected"]) is not bool or
                row["corrected"] != (obj.status != "active")):
            raise ValueError("corrected_flag_inconsistent")
        result.append(obj)
    return tuple(result)


def _validated(events: Sequence[PublicMemoryEvent]) -> dict[int, PublicMemoryEvent]:
    if (not isinstance(events, Sequence) or isinstance(events, (str, bytes)) or
            not 1 <= len(events) <= _MAX_ROWS):
        raise ValueError("invalid_memory_snapshot")
    lookup = {}
    for event in events:
        if not isinstance(event, PublicMemoryEvent):
            raise ValueError("invalid_memory_event")
        if event.event_id in lookup:
            raise ValueError("duplicate_memory_event")
        lookup[event.event_id] = event
    for event in events:
        if event.status == "superseded":
            next_event = lookup.get(event.superseded_by_id)
            if next_event is None:
                raise ValueError("missing_memory_replacement")
            if next_event.recorded_at > event.corrected_at:
                raise ValueError("replacement_recorded_after_correction")
            if next_event.corrected_at is not None and next_event.corrected_at < event.corrected_at:
                raise ValueError("replacement_corrected_before_predecessor")
    for event in events:
        seen = set()
        current = event
        while current.status == "superseded":
            if current.event_id in seen:
                raise ValueError("memory_supersession_cycle")
            seen.add(current.event_id)
            current = lookup[current.superseded_by_id]
    return lookup


def _fingerprint(by_id: dict[int, PublicMemoryEvent]) -> str:
    return sha256(_canonical({"domain": "klone-v30-memory-snapshot-lab",
        "events": [asdict(by_id[k]) for k in sorted(by_id)]})).hexdigest()


def check_memory_continuity(
    before: Sequence[PublicMemoryEvent], after: Sequence[PublicMemoryEvent],
) -> dict:
    """Fail closed on lost history, mutable corrections or resurrected facts.

    This comparison assumes complete, independently captured source snapshots.
    A partial list is NOT a trustworthy memory snapshot; adapter users must
    enforce completeness. No historical time travel is inferred from live rows.
    """
    first, second = _validated(before), _validated(after)
    problems = set()
    transitions = {"unchanged": 0, "new": 0, "new_rejections": 0,
                   "new_supersessions": 0}
    for key, old in first.items():
        current = second.get(key)
        if current is None:
            problems.add("previous_event_missing")
            continue
        if (old.recorded_at, old.occurred_at, old.room_id,
            old.classification_level) != (
                current.recorded_at, current.occurred_at,
                current.room_id, current.classification_level):
            problems.add("historical_event_metadata_changed")
        if old.status != "active":
            if current != old:
                problems.add("correction_rewritten_or_reactivated")
            else:
                transitions["unchanged"] += 1
        elif current.status == "active":
            transitions["unchanged"] += 1
        elif current.status == "rejected":
            if current.corrected_at < old.recorded_at:
                problems.add("invalid_rejection_time")
            transitions["new_rejections"] += 1
        elif current.status == "superseded":
            transitions["new_supersessions"] += 1
    transitions["new"] = len(second.keys() - first.keys())
    # Presence and signature may both be forged by a compromised source.
    report = {"schema_version": 1,
              "kind": "klone-memory-continuity-v30-lab",
              "before_sha256": _fingerprint(first),
              "after_sha256": _fingerprint(second),
              "previous_event_count": len(first),
              "current_event_count": len(second),
              "current_active_count": sum(e.status == "active" for e in second.values()),
              "current_corrected_count": sum(e.status != "active" for e in second.values()),
              "changes": transitions,
              "problems": sorted(problems),
              "continuity_status": "blocked" if problems else "consistent_for_review",
              "source_snapshot_authenticated": False,
              "historical_integrity_externally_anchored": False,
              "full_database_coverage_verified": False,
              "room_access_granted": False,
              "writes_performed": False,
              "automatic_memory_reactivation_allowed": False,
              "deployment_approval": False,
              "manual_review_required": True}
    report["report_sha256"] = sha256(_canonical({
        "domain": "klone-v30-continuity-report", "report": report})).hexdigest()
    return report


def verify_memory_continuity_report(
    before: Sequence[PublicMemoryEvent], after: Sequence[PublicMemoryEvent],
    reported: object,
) -> bool:
    """Deterministic replay only; NOT an authenticated proof of data origin."""
    if type(reported) is not dict:
        return False
    try:
        if len(_canonical(reported)) > 32768:
            return False
        expected = check_memory_continuity(before, after)
        return hmac.compare_digest(_canonical(reported), _canonical(expected))
    except (ValueError, TypeError, OverflowError, RecursionError):
        return False
