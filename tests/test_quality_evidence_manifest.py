import unittest

from klone.acceptance_matrix import DOMAINS
from klone.quality_evidence_manifest import fingerprint_evidence


class QualityEvidenceManifestTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.evidence = {
            domain: {"state": "unverified", "source": "", "reference": ""}
            for domain in DOMAINS
        }

    def test_deterministic_and_untrusted_by_default(self):
        self.evidence["ci"] = {
            "state": "passed", "source": "github_actions", "reference": "run:72"
        }
        first = fingerprint_evidence(commit=self.sha, domain_evidence=self.evidence)
        second = fingerprint_evidence(
            commit=self.sha, domain_evidence=dict(reversed(list(self.evidence.items())))
        )
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertFalse(first["authenticated"])
        self.assertFalse(first["deployment_approval"])

    def test_passed_without_reference_rejected(self):
        self.evidence["memory"]["state"] = "passed"
        with self.assertRaises(ValueError):
            fingerprint_evidence(commit=self.sha, domain_evidence=self.evidence)

    def test_missing_domain_rejected(self):
        self.evidence.pop("genomics")
        with self.assertRaises(ValueError):
            fingerprint_evidence(commit=self.sha, domain_evidence=self.evidence)

    def test_change_modifies_fingerprint(self):
        first = fingerprint_evidence(commit=self.sha, domain_evidence=self.evidence)
        self.evidence["research"]["state"] = "pending"
        second = fingerprint_evidence(commit=self.sha, domain_evidence=self.evidence)
        self.assertNotEqual(first["sha256"], second["sha256"])
