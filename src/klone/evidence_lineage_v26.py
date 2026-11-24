"""Conservative, read-only cross-module evidence dependency graph (v2.6 LAB).

Untrusted metadata, digests and source labels are *claims*, not attestation.
The report is neither a grant of access nor a proof of independent evidence.
No memory writes, model calls, network access, file I/O or execution.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from collections import defaultdict, deque
from collections.abc import Sequence

from .acceptance_matrix import DOMAINS

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_ROOM = {
    "public-room": "public", "restricted-room": "personal",
    "sealed-room": "intimate", "sandbox-room": "restricted_bio",
    "debug-room": "intimate",
}
_STANCES = frozenset({"supports", "contradicts", "unknown"})
_MAX_NODES = 512
_MAX_EDGES = 4096
_MAX_CLAIMS = 128


def _id(value: object) -> bool:
    return type(value) is str and bool(_ID.fullmatch(value))


@dataclass(frozen=True)
class EvidenceLineageNode:
    node_id: str
    claim_key: str
    domain: str
    source_group: str
    content_sha256: str
    stance: str
    room_id: str
    classification: str
    dependencies: tuple[str, ...] = ()
    supersedes: str | None = None

    def __post_init__(self) -> None:
        if any(not _id(value) for value in
               (self.node_id, self.claim_key, self.source_group)):
            raise ValueError("invalid_evidence_identifier")
        if type(self.domain) is not str or self.domain not in DOMAINS:
            raise ValueError("unknown_evidence_domain")
        if type(self.content_sha256) is not str or not _HEX.fullmatch(self.content_sha256):
            raise ValueError("invalid_content_digest")
        if type(self.stance) is not str or self.stance not in _STANCES:
            raise ValueError("invalid_evidence_stance")
        if (type(self.room_id) is not str or self.room_id not in _ROOM
                or self.classification != _ROOM[self.room_id]):
            raise ValueError("classification_room_mismatch")
        if (type(self.dependencies) is not tuple or len(self.dependencies) > 64
                or any(not _id(parent) for parent in self.dependencies)
                or len(set(self.dependencies)) != len(self.dependencies)):
            raise ValueError("invalid_evidence_dependencies")
        if self.supersedes is not None and not _id(self.supersedes):
            raise ValueError("invalid_supersession")
        if self.node_id in self.dependencies or self.node_id == self.supersedes:
            raise ValueError("self_reference_denied")


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def analyze_lineage(nodes: Sequence[EvidenceLineageNode], *,
                    minimum_candidate_clusters: int = 2) -> dict:
    """Collapse shared dependencies, duplicate digests and declared groups.

    Named roots do not establish independent origins; no permission is granted.
    Superseded nodes remain in the graph but do not cast active evidence votes.
    """
    if (not isinstance(nodes, Sequence) or isinstance(nodes, (str, bytes))
            or not 1 <= len(nodes) <= _MAX_NODES):
        raise ValueError("invalid_evidence_set")
    if (type(minimum_candidate_clusters) is not int
            or not 2 <= minimum_candidate_clusters <= 64):
        raise ValueError("invalid_candidate_cluster_floor")
    by_id = {}
    for row in nodes:
        if not isinstance(row, EvidenceLineageNode):
            raise ValueError("invalid_evidence_node")
        if row.node_id in by_id:
            raise ValueError("duplicate_evidence_id")
        by_id[row.node_id] = row
    if len({r.claim_key for r in by_id.values()}) > _MAX_CLAIMS:
        raise ValueError("too_many_claims")
    # This fingerprint binds exactly the *declared* evidence metadata, not
    # source authenticity. It is stable when rows and parent links reorder.
    declared = []
    for row in sorted(by_id.values(), key=lambda r: r.node_id):
        d = asdict(row)
        d["dependencies"] = sorted(row.dependencies)
        declared.append(d)
    input_fingerprint = sha256(_canonical(declared)).hexdigest()

    graph = defaultdict(list)
    indegree = {key: 0 for key in by_id}
    ref_edges = 0
    superseded = set()
    for node in by_id.values():
        for parent in node.dependencies:
            if parent not in by_id:
                raise ValueError("missing_evidence_dependency")
            graph[parent].append(node.node_id)
            indegree[node.node_id] += 1
            ref_edges += 1
        if node.supersedes is not None:
            if node.supersedes not in by_id:
                raise ValueError("missing_superseded_evidence")
            old = by_id[node.supersedes]
            if (old.claim_key, old.room_id, old.classification) != (
                    node.claim_key, node.room_id, node.classification):
                raise ValueError("cross_scope_supersession_denied")
            if node.supersedes in superseded:
                raise ValueError("forked_supersession_denied")
            superseded.add(node.supersedes)
            graph[node.supersedes].append(node.node_id)
            indegree[node.node_id] += 1
            ref_edges += 1
    if ref_edges > _MAX_EDGES:
        raise ValueError("too_many_evidence_edges")

    ready = deque(key for key in sorted(by_id) if indegree[key] == 0)
    visited = 0
    while ready:
        key = ready.popleft()
        visited += 1
        for child in graph[key]:
            indegree[child] -= 1
            if not indegree[child]:
                ready.append(child)
    if visited != len(by_id):
        raise ValueError("cyclic_evidence_lineage")

    parent = {key: key for key in by_id}
    def root(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def join(a: str, b: str) -> None:
        x, y = root(a), root(b)
        if x != y:
            parent[max(x, y)] = min(x, y)

    seen_hash = {}
    seen_group = {}
    for node in sorted(by_id.values(), key=lambda x: x.node_id):
        for x in node.dependencies:
            join(node.node_id, x)
        if node.supersedes is not None:
            join(node.node_id, node.supersedes)
        if node.content_sha256 in seen_hash:
            join(node.node_id, seen_hash[node.content_sha256])
        else:
            seen_hash[node.content_sha256] = node.node_id
        if node.source_group in seen_group:
            join(node.node_id, seen_group[node.source_group])
        else:
            seen_group[node.source_group] = node.node_id

    clusters = defaultdict(list)
    for node in by_id.values():
        clusters[root(node.node_id)].append(node)
    component_by_id = {n.node_id: key for key, group in clusters.items() for n in group}
    cross_zone_clusters = {
        key for key, group in clusters.items()
        if len({(n.room_id, n.classification) for n in group}) > 1
    }
    output = []
    for claim in sorted({r.claim_key for r in by_id.values()}):
        members = [x for x in by_id.values() if x.claim_key == claim]
        active = [x for x in members if x.node_id not in superseded]
        groups = defaultdict(set)
        for x in active:
            groups[component_by_id[x.node_id]].add(x.stance)
        support = sum("supports" in v for v in groups.values())
        oppose = sum("contradicts" in v for v in groups.values())
        unknown = sum("unknown" in v for v in groups.values())
        zones = {(x.room_id, x.classification) for x in members}
        quarantined = (len(zones) != 1 or
                       any(component_by_id[x.node_id] in cross_zone_clusters for x in members))
        if quarantined:
            status = "quarantined_cross_room_lineage"
        elif oppose or any(len(v) > 1 for v in groups.values()):
            status = "contested_requires_review"
        elif unknown:
            status = "unresolved_requires_review"
        elif support < minimum_candidate_clusters:
            status = "insufficient_distinct_lineages"
        else:
            status = "candidate_for_manual_review"
        output.append({
            "claim_key": claim, "domain_count": len({x.domain for x in members}),
            "active_evidence_count": len(active),
            "superseded_evidence_count": len(members) - len(active),
            "declared_source_group_count": len({x.source_group for x in active}),
            "conservatively_collapsed_cluster_count": len(groups),
            "supporting_clusters": support, "contradicting_clusters": oppose,
            "unknown_clusters": unknown,
            "single_cluster_withdrawal_changes_candidate":
                status == "candidate_for_manual_review" and support - 1 < minimum_candidate_clusters,
            "cross_room_or_classification_lineage": quarantined,
            "review_status": status,
        })
    document = {
        "schema_version": 1,
        "kind": "klone-crossdomain-lineage-v26-lab",
        "input_nodes": len(by_id), "input_edges": ref_edges,
        "declared_input_sha256": input_fingerprint,
        "all_dependency_clusters": len(clusters),
        "claims": output,
        "source_independence_authenticated": False,
        "source_digests_authenticated": False,
        "cross_room_access_granted": False,
        "manual_review_required": True,
        "execution_enabled": False,
        "approval_granted": False,
        "privacy_note": "Metadata only. Cross-zone links are quarantined; raw content never loaded.",
    }
    document["analysis_sha256"] = sha256(_canonical(document)).hexdigest()
    return document
