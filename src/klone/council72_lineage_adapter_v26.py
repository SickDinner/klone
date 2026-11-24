"""Read-only Council72 -> conservative evidence lineage adapter (v2.6 LAB).

Only replayable Council72 session reports may be projected. Source SHA-256
values come from an explicit caller-provided mapping and are NOT authenticated
by this module. Raw summaries, source references and dispatch messages do not
appear in output. This is not a verification or authorization service.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re

from .acceptance_matrix import DOMAINS
from .evidence_lineage_v26 import EvidenceLineageNode, analyze_lineage

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_CLASS_ROOM = {
    "public": ("public-room", "public"),
    "restricted": ("restricted-room", "personal"),
    "sealed": ("sealed-room", "intimate"),
}
_MAX_OBS = 256


def _nodes_from_normalized_observations(
    observations: Sequence[Mapping],
    *, digest_by_source_ref: Mapping[str, str],
    domain: str = "cognition",
) -> list[EvidenceLineageNode]:
    """Strict projection of already-normalized observations; no revalidation claim.

    Caller still MUST verify the enclosing session's deterministic replay.
    All source references must be present in the supplied digest map; invented
    SHA-256 values from strings are forbidden. This mapping is NOT attested.
    """
    if type(domain) is not str or domain not in DOMAINS:
        raise ValueError("invalid_projection_domain")
    if (not isinstance(observations, Sequence) or isinstance(observations, (str, bytes))
            or not 1 <= len(observations) <= _MAX_OBS):
        raise ValueError("invalid_observation_set")
    if (not isinstance(digest_by_source_ref, Mapping)
            or len(digest_by_source_ref) > _MAX_OBS
            or any(type(k) is not str or not k or type(v) is not str
                   or not _HASH.fullmatch(v)
                   for k, v in digest_by_source_ref.items())):
        raise ValueError("invalid_supplied_source_digests")
    required = set()
    nodes = []
    for observation in observations:
        if not isinstance(observation, Mapping):
            raise ValueError("invalid_normalized_observation")
        keys = ("id", "claim_key", "source_group", "source_ref", "stance", "classification")
        if any(type(observation.get(k)) is not str for k in keys):
            raise ValueError("invalid_normalized_observation")
        ref = observation["source_ref"]
        required.add(ref)
        if ref not in digest_by_source_ref:
            raise ValueError("source_digest_missing")
        item_class = observation["classification"]
        if item_class not in _CLASS_ROOM:
            raise ValueError("invalid_council_classification")
        room, classification = _CLASS_ROOM[item_class]
        old = observation.get("supersedes")
        if old is not None and type(old) is not str:
            raise ValueError("invalid_supersession")
        nodes.append(EvidenceLineageNode(
            node_id="obsv-" + observation["id"],
            claim_key="claim-" + observation["claim_key"],
            domain=domain,
            source_group="group-" + observation["source_group"],
            content_sha256=digest_by_source_ref[ref],
            stance=observation["stance"],
            room_id=room, classification=classification,
            supersedes=None if old is None else "obsv-" + old,
        ))
    if set(digest_by_source_ref) != required:
        raise ValueError("unexpected_source_digest_reference")
    return nodes


def project_replayable_council_session(
    session_report: dict, *,
    digest_by_source_ref: Mapping[str, str],
    domain: str = "cognition",
    minimum_candidate_clusters: int = 2,
) -> dict:
    """Replay-check session and project only evidence metadata.

    A replay proves consistent recomputation with current code/catalog; it
    does NOT prove the evidence, device, human, or source digest is genuine.
    """
    from .council72_session import session_replays, validate_step

    if type(session_report) is not dict or not session_replays(session_report):
        raise ValueError("unreplayable_council_session")
    request = session_report["request"]
    normalized = []
    for step in request["steps"]:
        normalized.extend(validate_step(step)["observations"])
    nodes = _nodes_from_normalized_observations(
        normalized, digest_by_source_ref=digest_by_source_ref, domain=domain)
    graph = analyze_lineage(nodes, minimum_candidate_clusters=minimum_candidate_clusters)
    synthetic = request["source_kind"] == "synthetic_fixture"
    return {
        "schema_version": 1,
        "kind": "klone-council72-lineage-projection-v26-lab",
        "session_trace_sha256": session_report["trace_sha256"],
        "lineage_report": graph,
        "session_report_replays": True,
        "observation_count": len(nodes),
        "digest_map_source_authenticated": False,
        "source_independence_authenticated": False,
        "session_source_kind": request["source_kind"],
        "eligible_for_real_world_use": False,
        "review_status": "simulation_only" if synthetic else "human_review_required",
        "raw_observations_exported": False,
        "memory_write_enabled": False,
        "execution_enabled": False,
        "approval_granted": False,
    }
