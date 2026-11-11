"""Deterministic, bounded, read-only research evidence graph.

Generic KLONE research primitive; nodes/edges are metadata only. No graph
relation is proof of ancestry, causality, identity or authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json


NODE_KINDS = frozenset({"sample", "publication", "source", "hypothesis", "claim", "event", "place"})
EDGE_KINDS = frozenset({"cites", "derived_from", "supports", "contradicts", "dated_to", "located_at"})


@dataclass(frozen=True)
class EvidenceNode:
    node_id: str
    kind: str
    label: str
    source_ref: str


@dataclass(frozen=True)
class EvidenceEdge:
    source_id: str
    target_id: str
    relation: str
    source_ref: str


def build_evidence_graph(
    nodes: tuple[EvidenceNode, ...], edges: tuple[EvidenceEdge, ...],
) -> dict[str, object]:
    """Validate graph provenance, return canonical digest and adjacency."""
    if not isinstance(nodes, tuple) or not isinstance(edges, tuple):
        raise ValueError("Expected immutable graph tuples")
    if len(nodes) > 5000 or len(edges) > 20000:
        raise ValueError("Graph size limit exceeded")
    by_id: dict[str, EvidenceNode] = {}
    for node in nodes:
        if not isinstance(node, EvidenceNode) or node.kind not in NODE_KINDS:
            raise ValueError("Invalid graph node")
        for field in ("node_id", "label", "source_ref"):
            value = getattr(node, field)
            if not isinstance(value, str) or not value.strip() or len(value) > 512:
                raise ValueError("Invalid node " + field)
        if node.node_id in by_id:
            raise ValueError("Duplicate graph node")
        by_id[node.node_id] = node
    seen = set()
    adjacency: dict[str, list[tuple[str, str]]] = {node_id: [] for node_id in by_id}
    for edge in edges:
        if not isinstance(edge, EvidenceEdge) or edge.relation not in EDGE_KINDS:
            raise ValueError("Invalid graph edge")
        if edge.source_id not in by_id or edge.target_id not in by_id:
            raise ValueError("Dangling graph edge")
        if edge.source_id == edge.target_id:
            raise ValueError("Self-referential graph edge")
        if not isinstance(edge.source_ref, str) or not edge.source_ref.strip() or len(edge.source_ref) > 512:
            raise ValueError("Edge requires provenance")
        key = (edge.source_id, edge.target_id, edge.relation, edge.source_ref)
        if key in seen:
            raise ValueError("Duplicate graph edge")
        seen.add(key)
        adjacency[edge.source_id].append((edge.relation, edge.target_id))
    ordered_nodes = sorted((n.node_id, n.kind, n.label, n.source_ref) for n in nodes)
    ordered_edges = sorted(seen)
    payload = json.dumps([ordered_nodes, ordered_edges], ensure_ascii=False, separators=(",", ":"))
    return {
        "fingerprint": sha256(payload.encode("utf-8")).hexdigest(),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "adjacency": {k: tuple(sorted(v)) for k, v in sorted(adjacency.items())},
        "inference": "none_metadata_graph_only",
    }


def trace_evidence(
    graph: dict[str, object], *, start_id: str, max_depth: int = 4,
) -> tuple[str, ...]:
    """Cycle-safe, deterministic reachability bounded by depth and graph size."""
    adjacency = graph.get("adjacency")
    if not isinstance(adjacency, dict) or start_id not in adjacency:
        raise ValueError("Unknown start node")
    if type(max_depth) is not int or not 0 <= max_depth <= 10:
        raise ValueError("Invalid traversal depth")
    visited = {start_id}
    frontier = {start_id}
    for _ in range(max_depth):
        following = set()
        for node_id in sorted(frontier):
            for relation, target in adjacency[node_id]:
                if target not in visited:
                    following.add(target)
        if not following:
            break
        visited.update(following)
        frontier = following
    return tuple(sorted(visited))
