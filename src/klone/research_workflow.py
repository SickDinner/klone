from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Sequence

from .audit import AuditService
from .hypervisor_audit_adapter import DurableHypervisorAudit, authorize_hypervisor_raw_output
from .hypervisor_runtime import HypervisorRuntime
from .hypervisor_dispatch import DispatchDenied
from .research_agent import ResearchAgent
from .research_files import load_research_texts
from .research_report import ResearchReport, build_research_report
from .research_memory import ResearchMemory
from .repository import KloneRepository


@dataclass(frozen=True)
class ResearchRun:
    report: ResearchReport
    audit_event_count: int
    report_version: int | None = None


def run_local_research(
    *, root: Path, relative_paths: Sequence[str], question: str,
    room_id: str, actor_role: str, trace_id: str,
    classification_level: str, database_path: Path,
    persist_report: bool = False,
) -> ResearchRun:
    """Synchronous local-only research with persistent SQLite audit.

    Caller must authenticate actor_role, authorize root and database_path,
    and isolate concurrent callers. No remote access or untrusted root.
    """
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        raise ValueError("Question must contain 1-500 characters")
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise ValueError("Trace ID is required")
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
    try:
        report = build_research_report(result)
        audit("completed", decision, "research.report")
    except Exception:
        audit("failed", decision, "research.report")
        raise
    report_version = None
    if persist_report:
        if room_id != "public-room" or classification_level != "public":
            raise DispatchDenied("Research persistence is public-room only")
        audit("delegated", decision, "research.memory")
        try:
            saved = ResearchMemory(database_path).save(report)
            report_version = saved.version
            audit("completed", decision, "research.memory")
        except Exception:
            audit("failed", decision, "research.memory")
            raise
    events = repository.list_audit_events(
        room_id=room_id, target_type="service_seam", limit=100,
    )
    count = sum(
        1 for event in events
        if event.get("metadata_json") and
        json.loads(event["metadata_json"]).get("trace_id") == trace_id
    )
    return ResearchRun(report=report, audit_event_count=count, report_version=report_version)
