import unittest
from klone.evidence_regression_graph import graph


def run(name, commit, syntax="passed"):
    return {"run_name": name, "commit": commit, "integrity_ok": True,
            "stage_statuses": {"syntax": syntax, "cognition": "passed",
                               "full": "passed", "local_deploy": "passed"}}


class RegressionGraphTests(unittest.TestCase):
    def test_regression_and_candidate_file_are_not_causal(self):
        a = "a" * 40
        b = "b" * 40
        result = graph([run("old", a), run("new", b, "failed")],
                       {b: ["src/klone/memory.py"]})
        self.assertTrue(any(n["kind"] == "regression" for n in result["nodes"]))
        self.assertTrue(any(n["kind"] == "candidate_file" for n in result["nodes"]))
        self.assertTrue(all(edge["causal"] is False for edge in result["edges"]))
        self.assertFalse(result["causality_established"])

    def test_empty_graph(self):
        self.assertEqual(graph([])["edges"], [])

    def test_invalid_run_rejected(self):
        with self.assertRaises(ValueError):
            graph(["invalid"])

    def test_no_approval(self):
        result = graph([run("one", "a" * 40)])
        self.assertFalse(result["deployment_approval"])
        self.assertFalse(result["origin_authenticated"])


if __name__ == "__main__":
    unittest.main()
