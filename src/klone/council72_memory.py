"""Explicit public-room count probe through the existing audited read pipeline."""
from uuid import uuid4
import json

from .cognition_memory import probe_memory
from .cognition_neurocortex import digest
from .council72 import catalog
from .guards import output_guard
from .hypervisor_runtime import HypervisorRuntime
from .hypervisor_safe_pipeline import SafeReadPipeline


def public_memory_observation(repository, *, limit=50):
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("memory sample limit must be between one and 200")
    trace_id = "council-memory-" + uuid4().hex

    def audit(event, route, seam):
        repository.record_audit_event(event_type="council72_memory_" + event,
            actor="council72-public-probe", target_type="service_seam", target_id=seam,
            room_id=route.room_id, classification_level="public",
            summary="Neuvosto 72: rajattu julkisen huoneen muistin lukumäärähavainto",
            metadata={"trace_id": trace_id, "limit": limit, "actor_authenticated": False})

    pipeline = SafeReadPipeline(runtime=HypervisorRuntime(),
        handlers={"MemoryFacade": lambda room: probe_memory(repository, room_id=room, limit=limit).public_summary()},
        audit=audit, authorize_output=lambda level: output_guard.evaluate(classification_level=level).decision)
    result = pipeline.read(seam="MemoryFacade", room_id="public-room", actor_role="evaluator",
                           trace_id=trace_id, classification_level="public")
    summary = dict(result.payload)
    signature = digest(summary)
    observation = {"id": "memory-" + signature[:48],
        "courier_id": catalog()["rings"][0]["member_ids"][2],
        "source_ref": "memory-probe:" + signature, "source_group": "klone-memory-core",
        "claim_key": "public-memory-sample", "stance": "unknown", "classification": "public",
        "summary": json.dumps(summary, ensure_ascii=False, sort_keys=True),
        "signals": {"evidence_quality": 0., "uncertainty": 1., "risk": .5}}
    return {"observation": observation, "sample": summary, "audit_trace_id": trace_id,
            "raw_memory_included": False, "provenance_authenticated": False,
            "note": "Lukumääräotos ei osoita sisällön laatua tai tutkimustavoitteen onnistumista."}
