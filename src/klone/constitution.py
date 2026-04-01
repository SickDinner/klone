from __future__ import annotations

from .schemas import (
    ConstitutionChangeRecord,
    ConstitutionParameterRecord,
    ConstitutionSnapshotRecord,
    PublicCapabilityRecord,
    ServiceSeamRecord,
)


CONSTITUTION_PROFILE_ID = "constitution:default"
CONSTITUTION_LAYER_VERSION = "2e.1.read_only_shell"


class ConstitutionService:
    def seam_descriptor(self) -> ServiceSeamRecord:
        return ServiceSeamRecord(
            id="constitution-service",
            name="ConstitutionService",
            implementation="in_process_read_only_shell",
            status="read_only_shell",
            notes=[
                "Separates slow-cycle model parameters from mutable memory and ingest evidence.",
                "Exposes a read-only snapshot and change log only; no write or routing authority exists yet.",
            ],
        )

    def public_capabilities(self) -> list[PublicCapabilityRecord]:
        return [
            PublicCapabilityRecord(
                id="constitution.snapshot.read",
                name="Constitution Snapshot",
                category="constitution",
                path="/api/constitution",
                methods=["GET"],
                read_only=True,
                room_scoped=False,
                status="available",
                description="Read the current slow-cycle constitution shell, parameter defaults, and append-only change notes.",
                backed_by=["ConstitutionService", "PolicyService"],
            ),
        ]

    def snapshot(self) -> ConstitutionSnapshotRecord:
        parameters = [
            ConstitutionParameterRecord(
                key="evidence_strictness",
                value=0.92,
                min_value=0.0,
                max_value=1.0,
                category="evidence",
                description="Biases the model toward source-linked explanations over speculative synthesis.",
            ),
            ConstitutionParameterRecord(
                key="privacy_bias",
                value=0.95,
                min_value=0.0,
                max_value=1.0,
                category="governance",
                description="Keeps sensitive layers conservative until an explicit room- and policy-approved reason exists.",
            ),
            ConstitutionParameterRecord(
                key="inhibition_weight",
                value=0.78,
                min_value=0.0,
                max_value=1.0,
                category="regulation",
                description="Favors deliberate restraint before widening scope, action, or interpretation.",
            ),
            ConstitutionParameterRecord(
                key="novelty_appetite",
                value=0.34,
                min_value=0.0,
                max_value=1.0,
                category="exploration",
                description="Keeps exploration available, but below evidence and privacy priorities in the current shell.",
            ),
            ConstitutionParameterRecord(
                key="focus_bias",
                value=0.67,
                min_value=0.0,
                max_value=1.0,
                category="attention",
                description="Prefers a narrow active task window over broad concurrent context blending.",
            ),
            ConstitutionParameterRecord(
                key="consolidation_bias",
                value=0.61,
                min_value=0.0,
                max_value=1.0,
                category="memory",
                description="Marks the future boundary where slow-cycle stabilization should stay distinct from ordinary memory rows.",
            ),
            ConstitutionParameterRecord(
                key="escalation_threshold",
                value=0.74,
                min_value=0.0,
                max_value=1.0,
                category="governance",
                description="Encourages explicit escalation when consequences are non-obvious or room boundaries are at risk.",
            ),
        ]
        changes = [
            ConstitutionChangeRecord(
                version="2e.1",
                changed_at="2026-04-01T00:00:00Z",
                actor="owner",
                summary="Bootstrap the read-only constitution shell as a distinct layer from memory and ingest.",
                effect_scope="model_shell_only",
                notes=[
                    "No write route is enabled.",
                    "No routing, retrieval, or answer-generation logic reads these values yet.",
                ],
            )
        ]
        return ConstitutionSnapshotRecord(
            profile_id=CONSTITUTION_PROFILE_ID,
            layer_version=CONSTITUTION_LAYER_VERSION,
            summary=(
                "Read-only constitution shell for slow-cycle model defaults, governance posture, and future "
                "change tracking. This layer is intentionally visible before it becomes mutable."
            ),
            approval_state="owner_reviewed_shell",
            read_only=True,
            routing_influence_enabled=False,
            parameter_count=len(parameters),
            change_count=len(changes),
            parameters=parameters,
            recent_changes=changes,
            notes=[
                "Constitution values are separate from memory rows and ingest evidence.",
                "This shell exists to make slow-cycle defaults inspectable before enabling updates.",
            ],
            warnings=[
                "No write path exists yet.",
                "No live model-routing influence is enabled yet.",
            ],
        )
