"""Proof that memory review stays uncertain and is accepted by real Council72 schema."""
import json
import unittest

from klone.memory_continuity_v30 import PublicMemoryEvent

T = "2026-11-24T08:00:00Z"

try:
    from klone.council72_memory_review_v30 import public_memory_continuity_observation
    from klone.council72_session import validate_step
except ImportError:
    public_memory_continuity_observation = validate_step = None


@unittest.skipIf(public_memory_continuity_observation is None, "full Council72 dependencies unavailable")
class PublicMemoryCouncilReviewV30Tests(unittest.TestCase):
    def event(self, i):
        return PublicMemoryEvent(event_id=i, recorded_at=T, occurred_at=T)

    def test_real_council_schema_accepts_unknown_only(self):
        report = public_memory_continuity_observation([self.event(1)], [self.event(1)])
        obs = report["observation"]
        normalized = validate_step({"observations": [obs]})
        self.assertEqual(normalized["observations"][0]["stance"], "unknown")
        self.assertFalse(report["approval_granted"])
        self.assertFalse(report["source_origin_authenticated"])
        self.assertFalse(report["council_vote_cast"])

    def test_missing_history_generates_risk_review_not_vote(self):
        report = public_memory_continuity_observation(
            [self.event(1), self.event(2)], [self.event(2)])
        self.assertEqual(report["continuity_status"], "blocked")
        self.assertEqual(report["observation"]["signals"]["risk"], 0.95)
        self.assertEqual(report["observation"]["stance"], "unknown")
        self.assertNotIn("evidence_text", json.dumps(report))
        self.assertFalse(report["memory_write_enabled"])

    def test_deterministic_and_no_authority(self):
        a = public_memory_continuity_observation([self.event(1)], [self.event(1)])
        b = public_memory_continuity_observation([self.event(1)], [self.event(1)])
        self.assertEqual(a, b)
        self.assertFalse(a["execution_enabled"])
        self.assertFalse(a["room_access_granted"])


if __name__ == "__main__":
    unittest.main()
