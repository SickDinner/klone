import unittest
from fastapi.testclient import TestClient
from klone.main import create_app


class CognitionApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_capabilities_disclaim_consciousness_and_writes(self):
        response = self.client.get("/api/cognition/capabilities")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["consciousness_claim"])
        self.assertFalse(response.json()["external_actions"])

    def test_simulation_is_deterministic(self):
        first = self.client.post("/api/cognition/simulate", json={"steps": 12})
        second = self.client.post("/api/cognition/simulate", json={"steps": 12})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertTrue(first.json()["replay_matches"])

    def test_input_is_bounded(self):
        response = self.client.post("/api/cognition/simulate", json={"steps": 10000})
        self.assertEqual(response.status_code, 422)

    def test_ablation(self):
        response = self.client.post("/api/cognition/ablations", json={"steps": 8})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 4)


if __name__ == "__main__":
    unittest.main()
