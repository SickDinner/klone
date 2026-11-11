"""Offline security policy regression tests: no real API keys or network traffic."""
from dataclasses import replace
from hashlib import sha256
import unittest

from klone.egress_policy import EgressRequest, PayloadPart, evaluate_egress, verify_serialized_payload
from klone.approval_policy import ApprovalProposal, advance_proposal


class EgressPolicyTests(unittest.TestCase):
    def request(self, classification="public_knowledge", room="public_room"):
        payload = b"synthetic public fixture"
        return EgressRequest(
            request_id="req-1", room_id="public_room", principal="tester", actor_role="owner",
            provider="example", model="mock", purpose="test", policy_version="s1",
            parts=(PayloadPart("system", classification, sha256(payload).hexdigest(), len(payload), room),),
            serialized_payload_sha256=sha256(payload).hexdigest(),
        )

    def test_default_deny_even_with_allowlist(self):
        decision = evaluate_egress(self.request(), allowlisted_destinations=frozenset({("example", "mock")}))
        self.assertEqual(decision.reason_code, "external_transport_disabled")

    def test_public_only_explicit_opt_in(self):
        decision = evaluate_egress(self.request(), external_enabled=True, allowlisted_destinations=frozenset({("example", "mock")}))
        self.assertTrue(decision.permitted)

    def test_sensitive_zones_never_external(self):
        for zone in ("sensitive_cognition", "restricted_bio"):
            with self.subTest(zone=zone):
                decision = evaluate_egress(self.request(zone), external_enabled=True, allowlisted_destinations=frozenset({("example", "mock")}))
                self.assertFalse(decision.permitted)

    def test_personal_data_requires_approval(self):
        self.assertEqual(evaluate_egress(self.request("personal_knowledge")).decision, "require_approval")

    def test_cross_room_rejected(self):
        self.assertEqual(evaluate_egress(self.request(room="sealed_room")).reason_code, "cross_room_source")

    def test_payload_tampering_rejected(self):
        expected = sha256(b"original").hexdigest()
        self.assertTrue(verify_serialized_payload(b"original", expected))
        self.assertFalse(verify_serialized_payload(b"modified", expected))

    def test_empty_manifest_denied(self):
        self.assertEqual(evaluate_egress(replace(self.request(), parts=())).reason_code, "invalid_manifest")

    def test_manifest_hash_deterministic(self):
        self.assertEqual(evaluate_egress(self.request()).manifest_sha256, evaluate_egress(self.request()).manifest_sha256)


class ApprovalPolicyTests(unittest.TestCase):
    def proposal(self):
        return ApprovalProposal("p1", "agent", "public_room", "v1", "a" * 64)

    def awaiting(self):
        p = self.proposal()
        p = advance_proposal(p, "validated", actor_id="agent")
        return advance_proposal(p, "awaiting_approval", actor_id="agent")

    def test_self_approval_denied(self):
        with self.assertRaises(PermissionError):
            advance_proposal(self.awaiting(), "approved", actor_id="agent", human_approved=True, current_target_version="v1", current_patch_sha256="a" * 64)

    def test_stale_version_denied(self):
        with self.assertRaises(ValueError):
            advance_proposal(self.awaiting(), "approved", actor_id="human", human_approved=True, current_target_version="v2", current_patch_sha256="a" * 64)

    def test_patch_change_denied(self):
        with self.assertRaises(ValueError):
            advance_proposal(self.awaiting(), "approved", actor_id="human", human_approved=True, current_target_version="v1", current_patch_sha256="b" * 64)

    def test_valid_approval_and_activation(self):
        p = advance_proposal(self.awaiting(), "approved", actor_id="human", human_approved=True, current_target_version="v1", current_patch_sha256="a" * 64)
        self.assertEqual(p.approver_id, "human")
        p = advance_proposal(p, "activating", actor_id="human", current_target_version="v1", current_patch_sha256="a" * 64)
        self.assertEqual(p.state, "activating")

    def test_replay_denied(self):
        p = advance_proposal(self.awaiting(), "approved", actor_id="human", human_approved=True, current_target_version="v1", current_patch_sha256="a" * 64)
        with self.assertRaises(ValueError):
            advance_proposal(p, "approved", actor_id="human", human_approved=True, current_target_version="v1", current_patch_sha256="a" * 64)


if __name__ == "__main__":
    unittest.main()
