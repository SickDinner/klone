"""Durable tracked execution for the Mission Control research service.

The journal must use the SAME SQLite database as the research dossier.
This adapter records started/completed/failed states but the journal's
completion, dossier commit and outbox enqueue are one SQLite transaction. Recovery
must treat an orphaned 'started' run as indeterminate, not failed.
"""
from __future__ import annotations

from dataclasses import dataclass

from .mission_control_research_service import (
    MissionControlResearchService, ResearchServiceRequest,
)
from .research_run_journal import ResearchRunJournal, RunEvent
from .research_source_manifest import PublicSourceManifest
from .integrated_research_core import IntegratedResearchResult
from .research_atomic_run import finalize_verified_run_atomically


@dataclass(frozen=True)
class TrackedResearchResult:
    run_id: str
    result: IntegratedResearchResult
    events: tuple[RunEvent, ...]


class MissionControlTrackedResearch:
    def __init__(self, *, service: MissionControlResearchService):
        if not isinstance(service, MissionControlResearchService):
            raise TypeError("Trusted research service required")
        self.service = service
        self.journal = ResearchRunJournal(service.database_path)

    def run(
        self, *, run_id: str, request: ResearchServiceRequest,
        json_text: str, manifests: dict[str, PublicSourceManifest],
        source_bytes: dict[str, bytes],
    ) -> TrackedResearchResult:
        # Deny BEFORE creating the journal entry or any other write.
        self.service._gate(request, "run")
        # A single started entry is a durable claim on run_id. Duplicate
        # submissions fail closed instead of silently appending versions.
        self.journal.transition(
            run_id=run_id, state="started", trace_id=request.trace_id,
            dossier_id=request.dossier_id)
        try:
            # Recheck live permissions. Dossier, completed run and audit
            # outbox event are committed in one SQLite transaction.
            self.service._gate(request, "run")
            result = finalize_verified_run_atomically(
                database_path=self.service.database_path,
                run_id=run_id, trace_id=request.trace_id,
                dossier_id=request.dossier_id, json_text=json_text,
                manifests=manifests, source_bytes=source_bytes)
            # External audit can fail after commit; outbox remains pending.
            self.service.audit("completed", request, "run")
        except Exception as exc:
            # The dossier MAY have committed before an exception. Do not
            # promise rollback or retry automatically.
            try:
                current = self.journal.history(run_id=run_id)
                if current and current[-1].state == "started":
                    self.journal.transition(
                        run_id=run_id, state="failed", trace_id=request.trace_id,
                        dossier_id=request.dossier_id,
                        detail=type(exc).__name__[:1000])
            except Exception:
                # Preserve the original failure; the run remains 'started'
                # and requires operator reconciliation.
                pass
            raise
        return TrackedResearchResult(
            run_id=run_id, result=result, events=self.journal.history(run_id=run_id))

    def history(self, *, run_id: str, request: ResearchServiceRequest) -> tuple[RunEvent, ...]:
        self.service._gate(request, "inspect")
        events = self.journal.history(run_id=run_id)
        # Do not reveal another research dossier's events.
        if any(e.dossier_id != request.dossier_id for e in events):
            raise PermissionError("Run belongs to another dossier")
        return events
