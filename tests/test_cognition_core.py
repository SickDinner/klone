import unittest

from klone.cognition_core import CognitionCore, compare_ablations


class CognitionCoreTests(unittest.TestCase):
    def test_deterministic_replay(self):
        core = CognitionCore()
        core.run(64)
        self.assertEqual(core.snapshot(), core.replay().snapshot())
        self.assertEqual(core.trace_digest(), core.replay().trace_digest())

    def test_capacity_bounds(self):
        core = CognitionCore(workspace_capacity=2, memory_capacity=3)
        core.run(50)
        self.assertLessEqual(len(core.state.workspace), 2)
        self.assertEqual(len(core.state.episodes), 3)

    def test_ablation_does_not_grant_capabilities(self):
        results = compare_ablations(12)
        self.assertEqual(set(results), {"full", "no_workspace", "no_memory", "no_self_model"})
        self.assertTrue(all(item["replay_matches"] for item in results.values()))
        self.assertEqual(results["no_workspace"]["state"]["workspace"], [])
        self.assertEqual(results["no_memory"]["state"]["episodes"], [])
        self.assertEqual(results["no_self_model"]["state"]["self_model"], {})

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError):
            CognitionCore(workspace_capacity=0)
        with self.assertRaises(ValueError):
            CognitionCore().run(1001)
        with self.assertRaises(ValueError):
            CognitionCore().step(1.1)
        with self.assertRaises(ValueError):
            CognitionCore().step(-0.1)


if __name__ == "__main__":
    unittest.main()
