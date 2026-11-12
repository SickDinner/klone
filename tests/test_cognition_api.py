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

    def test_learning_endpoint(self):
        first = self.client.post("/api/cognition/learn", json={"steps": 16, "seed": 72})
        second = self.client.post("/api/cognition/learn", json={"steps": 16, "seed": 72})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertIn("baseline", first.json())

    def test_learning_rejects_invalid(self):
        response = self.client.post("/api/cognition/learn", json={"steps": 501})
        self.assertEqual(response.status_code, 422)

    def test_ablation(self):
        response = self.client.post("/api/cognition/ablations", json={"steps": 8})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 4)


    def test_simulation_rejects_invalid_capacity_and_negative_steps(self):
        for payload in (
            {"steps": -1},
            {"steps": 201},
            {"workspace_capacity": 0},
            {"workspace_capacity": 65},
            {"memory_capacity": 0},
            {"memory_capacity": 10001},
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/api/cognition/simulate", json=payload)
                self.assertEqual(response.status_code, 422)

    def test_learning_rejects_invalid_seed_and_nonfinite_parameters(self):
        for payload in (
            {"seed": -1},
            {"seed": 4294967296},
            {"learning_rate": -0.01},
            {"learning_rate": 1.01},
            {"learning_rate": "NaN"},
            {"initial_prediction": "Infinity"},
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/api/cognition/learn", json=payload)
                self.assertEqual(response.status_code, 422)

    def test_planning_is_deterministic_and_rejects_nonfinite_inputs(self):
        payload = {"energy": 0.7, "uncertainty": 0.3, "horizon": 3}
        first = self.client.post("/api/cognition/plan", json=payload)
        second = self.client.post("/api/cognition/plan", json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        for invalid in (
            {"energy": "NaN"},
            {"uncertainty": "Infinity"},
            {"risk_weight": "-Infinity"},
            {"horizon": 6},
        ):
            with self.subTest(invalid=invalid):
                response = self.client.post("/api/cognition/plan", json=invalid)
                self.assertEqual(response.status_code, 422)

    def test_capabilities_explicitly_deny_persistence_and_memory_access(self):
        response = self.client.get("/api/cognition/capabilities")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["persistence"], "none")
        self.assertFalse(data["memory_access"])
        self.assertEqual(data["permissions"], "none granted")
        self.assertTrue(data["experimental"])

if __name__ == "__main__":
    unittest.main()
