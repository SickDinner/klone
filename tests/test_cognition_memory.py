import unittest
from klone.cognition_memory import MemoryProbe, probe_memory


class MemoryProbeTests(unittest.TestCase):
    def test_summary_never_contains_evidence_or_content(self):
        p = MemoryProbe("sealed-room", 2, 1, 0, 1, 50, False)
        self.assertEqual(p.public_summary()["event_count"], 2)
        self.assertNotIn("evidence_text", p.public_summary())

    def test_limit_validation_happens_before_database_access(self):
        with self.assertRaises(ValueError):
            probe_memory(None, "sealed-room", 0)
        with self.assertRaises(ValueError):
            probe_memory(None, "sealed-room", 201)


if __name__ == "__main__":
    unittest.main()
