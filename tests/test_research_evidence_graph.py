from __future__ import annotations
from dataclasses import replace
import unittest

from klone.research_evidence_graph import (
    EvidenceEdge, EvidenceNode, build_evidence_graph, trace_evidence,
)


def nodes():
    return (
        EvidenceNode("claim:1", "claim", "A claim", "doi:source"),
        EvidenceNode("paper:1", "publication", "Paper", "doi:source"),
        EvidenceNode("sample:1", "sample", "Sample", "AADR:sample"),
    )


def edges():
    return (
        EvidenceEdge("claim:1", "paper:1", "cites", "doi:source"),
        EvidenceEdge("paper:1", "sample:1", "derived_from", "doi:source"),
    )


class ResearchGraphTests(unittest.TestCase):
    def test_canonical_graph_and_traversal(self):
        a = build_evidence_graph(nodes(), edges())
        b = build_evidence_graph(tuple(reversed(nodes())), tuple(reversed(edges())))
        self.assertEqual(a["fingerprint"], b["fingerprint"])
        self.assertEqual(trace_evidence(a, start_id="claim:1"), ("claim:1", "paper:1", "sample:1"))
        self.assertEqual(trace_evidence(a, start_id="claim:1", max_depth=1),
                         ("claim:1", "paper:1"))
        self.assertEqual(a["inference"], "none_metadata_graph_only")

    def test_cycle_safe(self):
        graph = build_evidence_graph(
            nodes(), edges() + (EvidenceEdge("sample:1", "claim:1", "derived_from", "doi:source"),))
        self.assertEqual(len(trace_evidence(graph, start_id="claim:1", max_depth=10)), 3)

    def test_reject_dangling_and_missing_provenance(self):
        with self.assertRaises(ValueError):
            build_evidence_graph(nodes(), (EvidenceEdge("claim:1", "absent", "cites", "doi:x"),))
        with self.assertRaises(ValueError):
            build_evidence_graph(nodes(), (replace(edges()[0], source_ref=""),))
        with self.assertRaises(ValueError):
            build_evidence_graph(nodes(), edges() + (edges()[0],))
        with self.assertRaises(ValueError):
            build_evidence_graph(nodes() + (nodes()[0],), edges())

    def test_bounded_traversal(self):
        graph = build_evidence_graph(nodes(), edges())
        with self.assertRaises(ValueError):
            trace_evidence(graph, start_id="claim:1", max_depth=11)
        with self.assertRaises(ValueError):
            trace_evidence(graph, start_id="missing")


if __name__ == "__main__":
    unittest.main()
