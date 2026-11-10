from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .audit import AuditService
from .hypervisor_audit_adapter import DurableHypervisorAudit, authorize_hypervisor_raw_output
from .hypervisor_runtime import HypervisorRuntime
from .hypervisor_dispatch import DispatchDenied
from .research_agent import ResearchAgent
from .research_files import load_research_texts
from .research_report import ResearchReport, build_research_report
from .repository import KloneRepository


@dataclass(frozen=True)
class ResearchRun:
    report: ResearchReport
    audit_event_count: int


def run_local_research(
    *, root: Path, relative_paths: Sequence[str], question: str,
    room_id: str, actor_role: str, trace_id: str,
    classification_level: str, database_path: Path,
) -> ResearchRun:
    """Synchronous local-only research with persistent SQLite audit.

    Caller must authenticate actor_role, authorize root and database_path,
    and isolate concurrent callers. No remote access or untrusted root.
    """
    repository = KloneRepository(database_path)
    repository.initialize()
    audit = DurableHypervisorAudit(AuditService(repository))
    # Authorize before touching the filesystem. Audit this boundary even if
    # the later read or file loader fails.
    decision = HypervisorRuntime().plan(
        room_id=room_id, actor_role=actor_role, permission="read",
        trace_id=trace_id, classification_level=classification_level,
    )
    if decision.decision != "allowed" or authorize_hypervisor_raw_output(classification_level) != "allowed":
        if decision.classification is not None:
            audit("denied", decision, "research.files")
        raise DispatchDenied("Research file access denied")
    audit("delegated", decision, "research.files")
    try:
        sources = load_research_texts(
            root=root, relative_paths=relative_paths, room_id=room_id,
            classification=classification_level,
        )
        audit("completed", decision, "research.files")
    except Exception:
        audit("failed", decision, "research.files")
        raise
    agent = ResearchAgent(
        sources=sources, audit=audit,
        authorize_output=authorize_hypervisor_raw_output,
    )
    result = agent.search(
        question=question, room_id=room_id, actor_role=actor_role,
        trace_id=trace_id, classification_level=classification_level,
    )
    report = build_research_report(result)
    events = repository.list_audit_events(
        room_id=room_id, target_type="service_seam", limit=100,
    )
    count = sum(
        1 for event in events
        if event.get("metadata_json") and
        __import__("json").loads(event["metadata_json"]).get("trace_id") == trace_id
    )
    return ResearchRun(report=report, audit_event_count=count)
