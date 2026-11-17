"""Offline Council72 quality, three-turn debate and safe evidence tool tests.

No production HTTP requests, no API credentials, no external file mutation.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_council72_intelligence_bridge import (
    dossier, fake_ring, fake_founders
)
from klone.council72 import catalog
from klone.council72_intelligence_bridge import (
    API_APPROVAL, CouncilModelError, run_council, RING_SCHEMA, FOUNDER_SCHEMA
)
from klone.council72_quality_lab import (
    _validate_bundle, quality_assessment, evidence_tool,
    debate_preview, main as quality_main
)
from klone.council72_debate import (
    APPROVAL, PUBLIC_CONFIRM, TURN_SCHEMA, ARBITER_SCHEMA,
    _arbiter_check, _turn_check, run_debate, main as debate_main
)
from klone.limbo_council_workbench import _fingerprint


def fake_council():
    evidence = dossier()
    question = "Miten näiden kahden tutkimuksen lähdeväitteet pitäisi tarkistaa?"
    def sender(model, instructions, text, schema, api_key, max_tokens):
        data = json.loads(text)
        usage = {"input_tokens": 120, "output_tokens": 250,
                 "total_tokens": 370}
        if schema is RING_SCHEMA:
            ids = [x["member_id"] for x in data["eight_distinct_roles"]]
            output = fake_ring(data["ring_id"], ids)
            output["counterarguments"] = [
                "Vastakkaisen menetelmän perusteet on yhä tarkistettava."
            ]
            return output, usage, "ring-" + str(data["ring_id"])
        if schema is FOUNDER_SCHEMA:
            ids = [x["member_id"] for x in data["eight_founders"]]
            return fake_founders(ids), usage, "founders"
        raise AssertionError("unexpected model request")

    with patch.dict(os.environ, {"KLONE_COUNCIL72_API_APPROVAL": API_APPROVAL}):
        report = run_council(
            question, evidence, live=True, owner_confirms_public=True,
            api_key="mock-secret", network_sender=sender
        )
    return report, evidence


def fake_debate_turn(stance, members, refs=None):
    return {
        "stance": stance,
        "role_focus_ids": list(members)[:3],
        "arguments": [
            {
                "claim": "Yksi tekstiosuma ei todista väitettä.",
                "challenge_or_defense":
                    "Menetelmä ja alkuperäisversio pitää vielä tarkistaa.",
                "falsification_test":
                    "Vertaile PDF:n ja Atom-version taulukot sivukohtaisesti.",
                "source_card_ids": refs if refs is not None else ["card-1"],
            },
        ],
        "uncertainties": [
            "Alkuperäisen tutkimuksen todentaminen on yhä kesken."
        ],
    }


def fake_referee(refs=None):
    return {
        "decision": "owner_review_required",
        "improved_claims": [
            "Lähdeketjun varmistus täytyy erottaa mallin päätelmästä."
        ],
        "unresolved_disputes": [
            "Miten eri poimintamenetelmät vaikuttavat vastaavuuteen?"
        ],
        "falsifiable_next_tests": [
            "Tarkista molempien arXiv-versioiden julkaistu PDF-teksti."
        ],
        "source_card_ids": refs if refs is not None else ["card-1"],
        "independence_warning":
            "Kolme vuoroa tehtiin samalla mallilla; ei itsenäistä konsensusta.",
        "scientific_truth_verified": False,
    }


class QualityAndDebateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.evidence = fake_council()
        cls.members = {m["id"] for m in catalog()["members"]}

    def setUp(self):
        self.block = patch(
            "klone.council72_debate._network_response",
            side_effect=AssertionError("a test attempted real HTTP")
        )
        self.block.start()
        self.addCleanup(self.block.stop)

    def test_audit_sees_all_72_seats_and_8_founders(self):
        result = quality_assessment(self.report, self.evidence)
        self.assertEqual(result["kind"], "klone-council72-quality-lab-v1")
        self.assertEqual(result["role_count"], 72)
        self.assertEqual(len(result["role_assessments"]), 64)
        self.assertEqual(len(result["founder_positions"]), 8)
        self.assertEqual(len(result["ring_diagnostics"]), 8)
        self.assertFalse(result["scientific_truth_verified"])
        self.assertFalse(result["memory_write"])
        self.assertEqual(result["model_api_requests_performed"], 0)
        self.assertEqual(result["report_sha256"], _fingerprint({
            k:v for k,v in result.items() if k != "report_sha256"
        }))
        self.assertTrue(all(
            not r["citations_attached_to_individual_seat"]
            for r in result["role_assessments"]
        ))

    def test_audit_is_deterministic_and_does_not_make_factual_claims(self):
        first = quality_assessment(self.report, self.evidence)
        second = quality_assessment(self.report, self.evidence)
        self.assertEqual(first, second)
        self.assertFalse(first["citation_coverage"]["per_claim_source_authentication"])
        self.assertTrue(any(
            "NOT confirmed hallucinations" in text
            for text in first["heuristic_notes"]
        ))

    def test_refuses_tampered_model_report_or_evidence(self):
        tampered = deepcopy(self.report)
        tampered["ring_calls"][0]["eight_seat_assessments"][
            "seat_assessments"][0]["observation"] = "forged response"
        with self.assertRaisesRegex(CouncilModelError, "modified"):
            quality_assessment(tampered, self.evidence)
        tampered["report_sha256"] = _fingerprint({
            k:v for k,v in tampered.items() if k != "report_sha256"
        })
        with self.assertRaisesRegex(CouncilModelError, "checksum mismatch"):
            quality_assessment(tampered, self.evidence)
        altered_evidence = deepcopy(self.evidence)
        altered_evidence["cards"][0]["quote_sample_for_owner_review"] += " fake"
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            quality_assessment(self.report, altered_evidence)

    def test_refuses_different_model_or_different_question(self):
        tampered = deepcopy(self.report)
        tampered["question"] = "Different public question"
        tampered["report_sha256"] = _fingerprint({
            k:v for k,v in tampered.items() if k != "report_sha256"
        })
        with self.assertRaisesRegex(CouncilModelError, "request"):
            quality_assessment(tampered, self.evidence)
        tampered = deepcopy(self.report)
        tampered["model"] = "unknown-model"
        tampered["report_sha256"] = _fingerprint({
            k:v for k,v in tampered.items() if k != "report_sha256"
        })
        with self.assertRaisesRegex(CouncilModelError, "mismatch"):
            quality_assessment(tampered, self.evidence)

    def test_read_only_tools_allowlist_and_public_card_identity(self):
        member = next(iter(self.members))
        card = self.evidence["cards"][0]["candidate_id"]
        answer = evidence_tool(self.evidence, "card_lookup", card_id=card)
        self.assertEqual(answer["result"]["card"]["card_id"], card)
        self.assertEqual(answer["network_request_count"], 0)
        self.assertTrue(answer["read_only"])
        self.assertFalse(answer["memory_write"])
        self.assertEqual(evidence_tool(
            self.evidence, "discrepancy_counts"
        )["result"]["card_count"], 10)
        self.assertEqual(evidence_tool(
            self.evidence, "member_profile", member_id=member
        )["result"]["member_id"], member)
        with self.assertRaises(PermissionError):
            evidence_tool(self.evidence, "fetch_http_url")
        with self.assertRaises(ValueError):
            evidence_tool(self.evidence, "card_lookup", card_id="invented")
        with self.assertRaises(ValueError):
            evidence_tool(self.evidence, "member_profile", member_id=999)

    def test_debate_preview_zero_external_calls(self):
        preview = debate_preview(self.report, self.evidence)
        self.assertEqual(preview["mode"], "offline_no_model_calls")
        self.assertEqual(preview["new_paid_requests"], 0)
        self.assertEqual(len(preview["eight_ring_debate_axes"]), 8)
        self.assertEqual(len(preview["role_specialist_topics"]), 64)
        self.assertIn("card_lookup", preview["tools_available_read_only"])
        self.assertEqual(run_debate(
            self.report, self.evidence
        ), preview)

    def test_live_debate_requires_separate_approval_and_bound_checkpoint_dir(self):
        with self.assertRaisesRegex(PermissionError, "public-data"):
            run_debate(self.report, self.evidence, live=True)
        with patch.dict(os.environ, {
            "KLONE_COUNCIL72_DEBATE_APPROVAL": APPROVAL,
            "KLONE_COUNCIL72_CONFIRM_PUBLIC": PUBLIC_CONFIRM
        }):
            with self.assertRaisesRegex(PermissionError, "three-call"):
                run_debate(self.report, self.evidence, live=True,
                           owner_confirms_public=True)
            with self.assertRaisesRegex(ValueError, "checkpoint"):
                run_debate(self.report, self.evidence, live=True,
                           owner_confirms_public=True,
                           api_key="mock-key")
        with self.assertRaisesRegex(ValueError, "offline"):
            run_debate(self.report, self.evidence,
                       checkpoint_dir="unwanted")

    def test_three_real_model_turn_shapes_with_mocked_sender(self):
        calls = []
        def sender(model, instructions, payload, schema, api_key, tokens):
            self.assertEqual(model, "gpt-6-luna")
            self.assertEqual(api_key, "mock-key")
            self.assertIn("ring_context_unverified", payload)
            self.assertIn("seat_statements_unverified", payload)
            calls.append(schema)
            usage = {
                "input_tokens": 2000,
                "output_tokens": 700,
                "total_tokens": 2700
            }
            if schema is ARBITER_SCHEMA:
                return fake_referee(), usage, "referee"
            stance = (
                "cross_examination" if len(calls) == 1 else "defense"
            )
            return fake_debate_turn(
                stance, sorted(self.members)
            ), usage, "turn-" + str(len(calls))

        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "debate-state"
            with patch.dict(os.environ, {
                "KLONE_COUNCIL72_DEBATE_APPROVAL": APPROVAL,
                "KLONE_COUNCIL72_CONFIRM_PUBLIC": PUBLIC_CONFIRM
            }):
                answer = run_debate(
                    self.report, self.evidence, live=True,
                    owner_confirms_public=True, api_key="mock-key",
                    checkpoint_dir=state, network_sender=sender
                )
            self.assertEqual(len(calls), 3)
            self.assertEqual(answer["model_api_requests_performed"], 3)
            self.assertEqual(answer["model_api_responses_reused"], 0)
            self.assertEqual(len(answer["debate_turns"]), 3)
            self.assertFalse(answer["scientific_truth_verified"])
            self.assertFalse(answer["memory_write"])
            self.assertFalse(answer["real_independent_agents"])
            self.assertEqual(len(list(state.glob("*-accepted.json"))), 3)
            self.assertEqual(len(list(state.glob("*-received-unverified.json"))), 3)
            self.assertEqual(answer["debate_turns"][-1]["answer"]["decision"],
                             "owner_review_required")
            with patch.dict(os.environ, {
                "KLONE_COUNCIL72_DEBATE_APPROVAL": APPROVAL,
                "KLONE_COUNCIL72_CONFIRM_PUBLIC": PUBLIC_CONFIRM
            }):
                again = run_debate(
                    self.report, self.evidence, live=True,
                    owner_confirms_public=True, api_key="mock-key",
                    checkpoint_dir=state
                )
            self.assertEqual(again["model_api_requests_performed"], 0)
            self.assertEqual(again["model_api_responses_reused"], 3)

    def test_fabricated_source_or_role_rejected(self):
        valid = fake_debate_turn("cross_examination", sorted(self.members))
        valid["arguments"][0]["source_card_ids"] = ["fake-ref"]
        with self.assertRaisesRegex(CouncilModelError, "evidence ID"):
            _turn_check(valid, "cross_examination",
                        {"card-1"}, self.members)
        valid = fake_debate_turn("cross_examination", sorted(self.members))
        valid["role_focus_ids"] = [999]
        with self.assertRaisesRegex(CouncilModelError, "member role"):
            _turn_check(valid, "cross_examination",
                        {"card-1"}, self.members)

    def test_no_referee_may_claim_verified_or_approve(self):
        item = fake_referee()
        item["scientific_truth_verified"] = True
        with self.assertRaisesRegex(CouncilModelError, "authority"):
            _arbiter_check(item, {"card-1"})
        item = fake_referee()
        item["decision"] = "approved"
        with self.assertRaisesRegex(CouncilModelError, "authority"):
            _arbiter_check(item, {"card-1"})

    def test_rejected_reply_persists_and_never_automatically_rebills(self):
        calls = []
        def broken(model, instructions, payload, schema, api_key, tokens):
            calls.append("called")
            return fake_debate_turn(
                "cross_examination", sorted(self.members),
                refs=["invented-source"]
            ), {"input_tokens":100,"output_tokens":200,
                "total_tokens":300}, "response"
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "states"
            with patch.dict(os.environ, {
                "KLONE_COUNCIL72_DEBATE_APPROVAL": APPROVAL,
                "KLONE_COUNCIL72_CONFIRM_PUBLIC": PUBLIC_CONFIRM
            }):
                with self.assertRaisesRegex(CouncilModelError, "evidence ID"):
                    run_debate(
                        self.report, self.evidence, live=True,
                        owner_confirms_public=True, api_key="mock-key",
                        checkpoint_dir=state, network_sender=broken
                    )
                self.assertEqual(len(calls), 1)
                self.assertTrue((
                    state / "debate-cross_examination-received-unverified.json"
                ).exists())
                with self.assertRaisesRegex(CouncilModelError, "evidence ID"):
                    run_debate(
                        self.report, self.evidence, live=True,
                        owner_confirms_public=True, api_key="mock-key",
                        checkpoint_dir=state, network_sender=broken
                    )
                self.assertEqual(len(calls), 1)

    def test_quality_cli_and_debate_cli_preview_write_only_new_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "e11.json"
            report = root / "complete.json"
            out = root / "quality.json"
            preview_out = root / "debate.json"
            evidence.write_text(json.dumps(self.evidence), encoding="utf-8")
            report.write_text(json.dumps(self.report), encoding="utf-8")
            self.assertEqual(quality_main([
                "--evidence", str(evidence), "--report", str(report),
                "--mode", "assess", "--output", str(out)
            ]), 0)
            self.assertEqual(
                json.loads(out.read_text())["role_count"], 72
            )
            self.assertEqual(debate_main([
                "--report", str(report), "--evidence", str(evidence),
                "--output", str(preview_out)
            ]), 0)
            self.assertEqual(
                json.loads(preview_out.read_text())["mode"],
                "offline_no_model_calls"
            )
            with self.assertRaises(SystemExit):
                quality_main([
                    "--evidence", str(evidence), "--report", str(report),
                    "--mode", "assess", "--output", str(out)
                ])


if __name__ == "__main__":
    unittest.main()
