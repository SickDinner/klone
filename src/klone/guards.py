from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .config import settings
from .contracts import ClassificationLevel
from .rooms import room_registry
from .schemas import GovernanceGuardRecord, GuardResultRecord


class AccessGuard:
    name = "AccessGuard"
    description = "Checks room role access and permission compatibility without invoking any model."

    def evaluate(self, *, room_id: str, actor_role: str, requested_permission: str) -> GuardResultRecord:
        room = room_registry.get_room(room_id)
        if room is None:
            return GuardResultRecord(
                guard_name=self.name,
                decision="blocked",
                reason=f"Room {room_id} is not registered.",
                requires_supervisor=True,
            )
        if actor_role not in room.allowed_roles:
            return GuardResultRecord(
                guard_name=self.name,
                decision="blocked",
                reason=f"Role {actor_role} is not allowed in room {room.label}.",
                requires_supervisor=True,
            )
        if requested_permission not in room.permissions:
            return GuardResultRecord(
                guard_name=self.name,
                decision="requires_approval",
                reason=f"Permission {requested_permission} is outside the current room policy.",
                requires_supervisor=True,
            )
        return GuardResultRecord(
            guard_name=self.name,
            decision="allowed",
            reason=f"Role {actor_role} can use {requested_permission} in {room.label}.",
            requires_supervisor=False,
        )


class ClassificationGuard:
    name = "ClassificationGuard"
    description = "Ensures a dataset or artifact classification matches its governed room."

    def evaluate(self, *, classification_level: ClassificationLevel, room_id: str) -> GuardResultRecord:
        room = room_registry.get_room(room_id)
        if room is None:
            return GuardResultRecord(
                guard_name=self.name,
                decision="blocked",
                reason=f"Room {room_id} is not registered.",
                requires_supervisor=True,
            )
        if room.classification != classification_level:
            return GuardResultRecord(
                guard_name=self.name,
                decision="blocked",
                reason=(
                    f"Classification {classification_level} does not match room "
                    f"classification {room.classification}."
                ),
                requires_supervisor=True,
            )
        return GuardResultRecord(
            guard_name=self.name,
            decision="allowed",
            reason=f"Classification {classification_level} matches the room policy.",
            requires_supervisor=False,
        )


class AuditGuard:
    name = "AuditGuard"
    description = "Verifies that auditable actions carry the minimum deterministic context."

    def evaluate(
        self,
        *,
        event_type: str,
        actor: str,
        target_type: str,
        summary: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> GuardResultRecord:
        if not event_type.strip() or not actor.strip() or not target_type.strip():
            return GuardResultRecord(
                guard_name=self.name,
                decision="blocked",
                reason="Audit events require event_type, actor, and target_type.",
                requires_supervisor=True,
            )
        if not summary.strip():
            return GuardResultRecord(
                guard_name=self.name,
                decision="blocked",
                reason="Audit events require a non-empty summary.",
                requires_supervisor=True,
            )
        if metadata is not None and not isinstance(metadata, Mapping):
            return GuardResultRecord(
                guard_name=self.name,
                decision="blocked",
                reason="Audit metadata must be a structured mapping.",
                requires_supervisor=True,
            )
        return GuardResultRecord(
            guard_name=self.name,
            decision="allowed",
            reason="Audit payload is structurally valid.",
            requires_supervisor=False,
        )


class OutputGuard:
    name = "OutputGuard"
    description = "Determines whether responses can include raw details or must stay summary-only."

    def evaluate(self, *, classification_level: ClassificationLevel) -> GuardResultRecord:
        if classification_level == "restricted_bio" and not settings.owner_debug_mode:
            return GuardResultRecord(
                guard_name=self.name,
                decision="summary_only",
                reason="Restricted bio output stays summary-only outside owner debug mode.",
                requires_supervisor=True,
            )
        if classification_level == "intimate" and not settings.owner_debug_mode:
            return GuardResultRecord(
                guard_name=self.name,
                decision="requires_approval",
                reason="Intimate data output requires supervisor review outside owner debug mode.",
                requires_supervisor=True,
            )
        return GuardResultRecord(
            guard_name=self.name,
            decision="allowed",
            reason="Output can include full indexed details in the current debug context.",
            requires_supervisor=False,
        )

    def sanitize_record(
        self,
        record: Mapping[str, Any],
        *,
        classification_level: ClassificationLevel,
    ) -> tuple[dict[str, Any], GuardResultRecord]:
        decision = self.evaluate(classification_level=classification_level)
        sanitized = dict(record)
        if decision.decision == "summary_only":
            sanitized["path"] = "[summary-only]"
            sanitized["metadata"] = {"policy": "summary_only"}
        return sanitized, decision


access_guard = AccessGuard()
classification_guard = ClassificationGuard()
audit_guard = AuditGuard()
output_guard = OutputGuard()


def governance_guard_catalog() -> list[GovernanceGuardRecord]:
    return [
        GovernanceGuardRecord(name=guard.name, description=guard.description, active=True)
        for guard in (access_guard, classification_guard, audit_guard, output_guard)
    ]
