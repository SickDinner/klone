"""HTTP integration smoke tests for the read-only Council72 cross-review."""
import unittest

from fastapi.testclient import TestClient

from klone.main import create_app
from klone.council72 import demo_proposal


class CouncilCrossReviewApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_endpoint_exposes_64_review_cells_without_permissions(self):
        r = self.client.post(
            "/api/cognition/council72/cross-review", json=demo_proposal()
        )
        self.assertEqual(r.status_code, 200)
        report = r.json()
        self.assertEqual(report["kind"], "klone-council72-cross-review")
        self.assertEqual(report["topology"]["unique_members"], 72)
        self.assertEqual(report["cross_checks"]["specialist_cells_evaluated"], 64)
        self.assertEqual(len(report["founder_line_views"]), 8)
        self.assertFalse(report["deployment_approval"])
        self.assertFalse(report["external_actions"])
        self.assertFalse(report["advisory"]["autonomous_release_allowed"])

    def test_request_is_deterministic_and_rejects_authority_injection(self):
        payload = demo_proposal()
        a = self.client.post("/api/cognition/council72/cross-review", json=payload)
        b = self.client.post("/api/cognition/council72/cross-review", json=payload)
        self.assertEqual(a.json(), b.json())
        response = self.client.post(
            "/api/cognition/council72/cross-review",
            json={**payload, "deployment_approval": True},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
