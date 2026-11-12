import unittest

from klone.evidence_network import STAGES, canonical, sha256
from klone.evidence_triage import triage, html_report


def packet(commit, failed=(), optional="not_present", suffix=""):
    statuses = {n: ("failed" if n in failed else "passed") for n in STAGES}
    statuses["torch_probe"] = optional
    value = {"schema_version": 1, "kind": "klone-evidence-packet",
             "commit": commit, "stages": statuses,
             "files": {n + ".log": {"sha256": sha256((n + suffix).encode()), "bytes": 3}
                       for n in STAGES},
             "overall": "failed" if failed else "passed",
             "origin_authentication": "not_provided",
             "device_identity_verified": False, "deployment_approval": False}
    value["packet_sha256"] = sha256(canonical(value))
    return value


class EvidenceTriageTests(unittest.TestCase):
    def test_regression_hint_and_no_authorization(self):
        result = triage(packet("a" * 40), packet("b" * 40, failed=("full",)))
        self.assertEqual(result["verdict"], "review_regression")
        self.assertEqual(result["hints"][0]["stage"], "full")
        self.assertFalse(result["causality_established"])
        self.assertFalse(result["patch_authorized"])
        self.assertFalse(result["deployment_approval"])

    def test_log_changes_do_not_prove_regression(self):
        result = triage(packet("a" * 40), packet("b" * 40, suffix="changed"))
        self.assertEqual(result["verdict"], "review_changed_logs")
        self.assertEqual(result["hints"], [])

    def test_no_change(self):
        result = triage(packet("a" * 40), packet("b" * 40))
        self.assertEqual(result["verdict"], "no_stage_regression_detected")

    def test_optional_probe_is_not_required_regression(self):
        result = triage(packet("a" * 40), packet("b" * 40, optional="unavailable"))
        self.assertEqual(result["verdict"], "no_stage_regression_detected")
        self.assertEqual(result["hints"][0]["confidence"], "optional_capability_only")

    def test_html_escapes_untrusted_values(self):
        result = triage(packet("a" * 40), packet("b" * 40))
        result["hints"].append({"stage": "<script>alert(1)</script>",
                                "area": "x", "location_hint": "x", "next_step": "x"})
        html = html_report(result)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)


if __name__ == "__main__":
    unittest.main()
