"""Council72 Intelligence Bridge: real API requests are always mocked in tests."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from klone.council72_intelligence_bridge import (
    API_APPROVAL, FOUNDER_SCHEMA, RING_SCHEMA,
    _fingerprinted_report, _network_response,
    _validate_founders, _validate_seats, CouncilModelError, main,
    run_council,
)
from klone.council72 import catalog
from klone.limbo_council_workbench import _fingerprint


def dossier():
    obj = {
        "kind": "klone-e11-11-arxiv-abstract-pdf-discrepancy-audit",
        "schema_version": 1,
        "e11_10_report_sha256": "a" * 64,
        "e11_9_report_sha256": "b" * 64,
        "e11_6_atom_receipt_sha256": "c" * 64,
        "source_snapshot_sha256": "d" * 64,
        "scientifically_verified_claims": 0,
        "council_reviews_performed": 0,
        "new_network_requests": 0,
        "memory_write": False,
        "original_pdf_publisher_authenticated": False,
        "sources": {
            "A": {"arxiv_id": "2611.13801v1",
                  "local_pdf_sha256": "1" * 64},
            "B": {"arxiv_id": "2611.15598v1",
                  "local_pdf_sha256": "2" * 64},
        },
        "card_count": 10,
        "cards": [
            {
                "candidate_id": "card-" + str(i),
                "source": "A" if i % 2 == 0 else "B",
                "arxiv_id": ("2611.13801v1" if i % 2 == 0
                             else "2611.15598v1"),
                "quote_sample_for_owner_review":
                    "This is an unverified local summary, not verified truth.",
                "quote_sha256": sha256(
                    ("Sample " + str(i)).encode()).hexdigest(),
                "discrepancy_class":
                    "no_textual_correspondence_found_not_disproved",
                "literal_pdf_pages": [],
                "typography_normalized_pdf_pages": [],
                "numeric_pdf_pages": ([1] if i == 0 else []),
                "scientific_claim_verified": False,
                "council_review_completed": False,
            } for i in range(10)
        ],
    }
    obj["report_sha256"] = _fingerprint(obj)
    return obj


def fake_ring(ring_id, role_ids, refs=None):
    return {
        "ring_id": ring_id,
        "seat_assessments": [
            {"member_id": mid,
             "observation": "Analysoin lähdepuutteita varovaisesti.",
             "challenge": "Mikä riippumaton näyttö puuttuu?"}
            for mid in role_ids
        ],
        "findings": ["Alkuperäisväitettä ei ole itsenäisesti vahvistettu."],
        "counterarguments": ["PDF-tekstiosuman puuttuminen ei ole vastanäyttö."],
        "open_questions": ["Tarkista menetelmät ja arvioinnin metriikat."],
        "evidence_card_ids": refs if refs is not None else ["card-0"],
        "uncertainty_note": "Kaikki ovat kielimallin testilausuntoja.",
    }


def fake_founders(founder_ids, refs=None):
    return {
        "founder_positions": [
            {"member_id": member_id, "position": "defer",
             "reason": "Ei riippumatonta alkuperäislähteen tarkistusta."}
            for member_id in founder_ids
        ],
        "synthesis": "Tarvitaan omistajan arvio ennen muita toimia.",
        "disagreements": ["Eri rinkien alustava näkökulma voi erota."],
        "next_experiments": ["Tarkista mittarit alkuperäisestä tutkimuksesta."],
        "evidence_card_ids": refs if refs is not None else ["card-1"],
        "decision": "owner_review_required",
    }


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.dossier = dossier()
        self.question = "Mitä eri tutkimusten metodologiasta voidaan varovasti päätellä?"
        self.model = catalog()
        self.members = {m["id"]:m for m in self.model["members"]}

    def test_offline_preview_zero_requests_no_secret_needed(self):
        result = run_council(self.question, self.dossier)
        self.assertEqual(result["mode"], "preview_no_network")
        self.assertEqual(result["planned_api_requests"], 9)
        self.assertEqual(result["model_api_requests_performed"], 0)
        self.assertEqual(len(result["ring_prompts"]), 8)
        self.assertEqual(len(set(
            mid for ring in result["ring_prompts"] for mid in ring["seat_ids"]
        )), 64)
        self.assertEqual(len(result["founder_ids"]), 8)
        self.assertFalse(result["scientific_truth_verified"])
        self.assertFalse(result["memory_write"])
        self.assertEqual(result, run_council(self.question, self.dossier))
        self.assertEqual(result["report_sha256"], _fingerprint({
            k:v for k,v in result.items() if k != "report_sha256"}))

    def test_live_requires_public_owner_confirmation_and_key_and_approval(self):
        with self.assertRaisesRegex(PermissionError, "public-data"):
            run_council(self.question, self.dossier, live=True)
        with self.assertRaisesRegex(PermissionError, "nine-request"):
            run_council(self.question, self.dossier, live=True,
                        owner_confirms_public=True, api_key="fake-secret")
        with patch.dict(os.environ, {"KLONE_COUNCIL72_API_APPROVAL": API_APPROVAL}):
            with self.assertRaisesRegex(PermissionError, "nine-request"):
                run_council(self.question, self.dossier, live=True,
                            owner_confirms_public=True)

    def test_mocked_live_creates_exactly_nine_analyses_and_no_votes(self):
        calls = []
        def send(model, instruction, text, schema, api_key, limit):
            calls.append((schema, text))
            self.assertEqual(model, "gpt-6-luna")
            self.assertEqual(api_key, "mock-key")
            if schema is RING_SCHEMA:
                data = json.loads(text)
                mid = [item["member_id"] for item in data["eight_distinct_roles"]]
                return fake_ring(data["ring_id"], mid), {
                    "input_tokens": 300, "output_tokens": 120,
                    "total_tokens": 420
                }, "resp" + str(len(calls))
            self.assertIs(schema, FOUNDER_SCHEMA)
            data = json.loads(text)
            mids = [member["member_id"] for member in data["eight_founders"]]
            self.assertEqual(len(data["ring_analyses_unverified"]), 8)
            return fake_founders(mids), {
                "input_tokens": 1200, "output_tokens": 400,
                "total_tokens": 1600
            }, "resp9"
        with patch.dict(os.environ, {"KLONE_COUNCIL72_API_APPROVAL": API_APPROVAL}):
            result = run_council(
                self.question, self.dossier, live=True,
                owner_confirms_public=True, api_key="mock-key",
                network_sender=send)
        self.assertEqual(len(calls), 9)
        self.assertEqual(result["model_api_requests_performed"], 9)
        self.assertEqual(result["seat_count"], 72)
        self.assertEqual(len(result["ring_calls"]), 8)
        self.assertFalse(result["real_independent_72_llm_agents"])
        self.assertEqual(result["founder_synthesis"]["decision"],
                         "owner_review_required")
        self.assertFalse(result["scientific_truth_verified"])
        self.assertFalse(result["memory_write"])
        self.assertEqual(result["external_messages_sent"], 0)
        self.assertEqual(result["council_binding_votes"], 0)
        self.assertFalse(result["responses_store_requested"])

    def test_wrong_role_and_fabricated_source_id_rejected(self):
        ring = self.model["rings"][0]
        fake = fake_ring(1, ring["member_ids"])
        fake["seat_assessments"][0]["member_id"] = 72
        with self.assertRaisesRegex(CouncilModelError, "missed or invented"):
            _validate_seats(fake, self.members, ring, {"card-0"})
        fake = fake_ring(1, ring["member_ids"], ["fabricated-source"])
        with self.assertRaisesRegex(CouncilModelError, "outside"):
            _validate_seats(fake, self.members, ring, {"card-0"})

    def test_refuses_forged_or_duplicated_founders(self):
        valid = fake_founders(self.model["founder_ids"])
        valid["founder_positions"][0]["member_id"] = 999
        with self.assertRaisesRegex(CouncilModelError, "founder identity"):
            _validate_founders(valid, self.model["founder_ids"], {"card-1"})
        invalid = fake_founders(self.model["founder_ids"])
        invalid["decision"] = "publish"
        with self.assertRaisesRegex(CouncilModelError, "cannot approve"):
            _validate_founders(invalid, self.model["founder_ids"], {"card-1"})

    def test_changed_evidence_fail_closed_before_any_model_call(self):
        tampered = deepcopy(self.dossier)
        tampered["cards"][0]["quote_sample_for_owner_review"] += " new"
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            run_council(self.question, tampered)
        tampered = deepcopy(self.dossier)
        tampered["cards"][0]["candidate_id"] = "card-1"
        tampered["report_sha256"] = _fingerprint({
            k:v for k,v in tampered.items() if k != "report_sha256"})
        with self.assertRaisesRegex(ValueError, "invalid card"):
            run_council(self.question, tampered)
        tampered = deepcopy(self.dossier)
        tampered["scientifically_verified_claims"] = 1
        tampered["report_sha256"] = _fingerprint({
            k:v for k,v in tampered.items() if k != "report_sha256"})
        with self.assertRaisesRegex(ValueError, "authority"):
            run_council(self.question, tampered)

    def test_rejects_unapproved_model_and_bad_question(self):
        with self.assertRaisesRegex(ValueError, "model"):
            run_council(self.question, self.dossier, model="evil-host")
        with self.assertRaisesRegex(ValueError, "question"):
            run_council("", self.dossier)
        with self.assertRaisesRegex(ValueError, "question"):
            run_council("x" * 1001, self.dossier)

    def test_fails_closed_after_bad_model_response_and_stops_calls(self):
        calls = []
        def wrong(model, instruction, text, schema, api_key, limit):
            calls.append(1)
            data = json.loads(text)
            return fake_ring(data["ring_id"],
                             [m["member_id"] for m in data["eight_distinct_roles"]],
                             ["invented-id"]), {}, "resp"
        with patch.dict(os.environ, {"KLONE_COUNCIL72_API_APPROVAL": API_APPROVAL}):
            with self.assertRaisesRegex(CouncilModelError, "outside"):
                run_council(self.question, self.dossier, live=True,
                            owner_confirms_public=True, api_key="mock-key",
                            network_sender=wrong)
        self.assertEqual(len(calls), 1)

    def test_responses_client_disables_tools_and_storage(self):
        from klone import council72_intelligence_bridge as bridge
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, length):
                return json.dumps({
                    "status": "completed", "error": None, "id": "res-1",
                    "output": [{"type":"message","content":[{
                        "type":"output_text", "text":json.dumps({"x": "y"})
                    }]}],
                    "usage":{"input_tokens":10,"output_tokens":15,
                             "total_tokens":25},
                }).encode()
        class Opener:
            def open(self, req, timeout=None):
                self_ref[0] = req
                return Response()
        self_ref = [None]
        with patch.object(bridge.urllib.request, "build_opener",
                          return_value=Opener()):
            answer, usage, identity = _network_response(
                "gpt-6-luna", "instruction", "test text",
                {"type":"object", "properties":{},
                 "required":[], "additionalProperties":False},
                "never-print-this-key", 1200)
        request = self_ref[0]
        self.assertEqual(request.full_url, bridge.ENDPOINT)
        self.assertEqual(request.get_method(), "POST")
        payload = json.loads(request.data)
        self.assertFalse(payload["store"])
        self.assertEqual(payload["tools"], [])
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertNotIn("never-print-this-key", json.dumps(payload))
        self.assertEqual(answer["x"], "y")
        self.assertEqual(identity, "res-1")
        self.assertEqual(usage["total_tokens"], 25)

    def test_cli_preview_does_not_call_openai_and_never_overwrites(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        path = root / "e1111.json"
        path.write_text(json.dumps(self.dossier, ensure_ascii=False))
        dest = root / "preview.json"
        args = ["--evidence", str(path), "--question", self.question,
                "--output", str(dest)]
        with patch("klone.council72_intelligence_bridge._network_response",
                   side_effect=AssertionError("network called during preview")):
            self.assertEqual(main(args), 0)
            previous = dest.read_bytes()
            with self.assertRaises(SystemExit):
                main(args)
        self.assertEqual(previous, dest.read_bytes())
        self.assertEqual(json.loads(previous)["model_api_requests_performed"], 0)


if __name__ == "__main__":
    unittest.main()
