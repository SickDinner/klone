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
        # Never let any unit test reach a real HTTP client, even if the user's
        # shell contains a valid API key and the full live approval flags.
        self._block_http = patch(
            "klone.council72_intelligence_bridge.urllib.request.build_opener",
            side_effect=AssertionError("unit test attempted a real HTTP request"),
        )
        self._block_http.start()
        self.addCleanup(self._block_http.stop)
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

    @patch.dict(os.environ, {"KLONE_COUNCIL72_API_APPROVAL": ""})
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
        self.assertEqual(payload["reasoning"]["effort"], "none")
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertNotIn("never-print-this-key", json.dumps(payload))
        self.assertEqual(answer["x"], "y")
        self.assertEqual(identity, "res-1")
        self.assertEqual(usage["total_tokens"], 25)

    def test_probe_requires_separate_one_call_owner_approval(self):
        with patch.dict(os.environ, {
            "KLONE_COUNCIL72_API_APPROVAL": API_APPROVAL,
            "KLONE_COUNCIL72_PROBE_APPROVAL": ""
        }):
            with self.assertRaisesRegex(PermissionError, "one-request"):
                run_council(
                    self.question, self.dossier, probe=True,
                    owner_confirms_public=True, api_key="mock-key"
                )
        with self.assertRaisesRegex(ValueError, "probe OR full"):
            run_council(self.question, self.dossier, live=True, probe=True)

    def test_mocked_probe_one_ring_eight_seats_no_founder_call(self):
        calls = []
        def sender(model, instruction, text, schema, api_key, limit):
            calls.append(text)
            self.assertIs(schema, RING_SCHEMA)
            data = json.loads(text)
            ids = [item["member_id"] for item in data["eight_distinct_roles"]]
            return fake_ring(data["ring_id"], ids), {
                "input_tokens": 150, "output_tokens": 360,
                "total_tokens": 510,
            }, "resp-probe"
        with patch.dict(os.environ, {
            "KLONE_COUNCIL72_PROBE_APPROVAL": "HYVAKSY_1_GPT_KUTSU"
        }):
            result = run_council(
                self.question, self.dossier, probe=True,
                owner_confirms_public=True, api_key="mock-key",
                network_sender=sender
            )
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["model_api_requests_performed"], 1)
        self.assertEqual(result["mode"], "api_one_ring_probe_completed")
        self.assertEqual(result["ring_calls"][0]["ring_id"], 1)
        self.assertEqual(
            len(result["ring_calls"][0]["eight_seat_assessments"]["seat_assessments"]), 8
        )
        self.assertNotIn("founder_synthesis", result)
        self.assertFalse(result["memory_write"])
        self.assertEqual(result["council_binding_votes"], 0)

    def test_incomplete_status_reports_only_safe_reason_and_usage(self):
        from klone import council72_intelligence_bridge as bridge
        class IncompleteResponse:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, length):
                return json.dumps({
                    "status": "incomplete",
                    "incomplete_details": {"reason": "max_output_tokens"},
                    "error": None,
                    "output": [{"type": "message",
                                "content": [{"type": "output_text",
                                             "text": "SECRET-MODEL-EXCERPT"}]}],
                    "usage": {
                        "input_tokens": 234,
                        "output_tokens": 1700,
                        "output_tokens_details": {"reasoning_tokens": 1450}
                    }
                }).encode()
        class Opener:
            def open(self, req, timeout=None):
                return IncompleteResponse()
        with patch.object(
            bridge.urllib.request, "build_opener",
            return_value=Opener()
        ):
            with self.assertRaisesRegex(CouncilModelError, "reason=max_output_tokens") as caught:
                _network_response(
                    "gpt-6-luna", "instruction", "input",
                    {"type": "object", "properties": {}, "required": [],
                     "additionalProperties": False}, "mock-key", 3400
                )
        message = str(caught.exception)
        self.assertIn("output_tokens=1700", message)
        self.assertIn("reasoning_tokens=1450", message)
        self.assertNotIn("SECRET", message)
        self.assertNotIn("mock-key", message)

    def test_probed_cli_creates_report_without_network(self):
        from klone import council72_intelligence_bridge as bridge
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "e1111.json"
            out = root / "probe.json"
            evidence.write_text(json.dumps(self.dossier), encoding="utf-8")
            def sender(model, instruction, text, schema, api_key, max_output_tokens):
                data = json.loads(text)
                return fake_ring(
                    data["ring_id"],
                    [x["member_id"] for x in data["eight_distinct_roles"]]
                ), {"input_tokens": 100, "output_tokens": 200,
                    "total_tokens": 300}, "mock-response"
            with patch.object(bridge, "_network_response", side_effect=sender):
                with patch.dict(os.environ, {
                    "KLONE_COUNCIL72_PROBE_APPROVAL": "HYVAKSY_1_GPT_KUTSU",
                    "OPENAI_API_KEY": "mock-key"
                }):
                    self.assertEqual(main([
                        "--evidence", str(evidence),
                        "--question", self.question, "--output", str(out),
                        "--probe", "--owner-confirms-public-data"
                    ]), 0)
            self.assertEqual(
                json.loads(out.read_text(encoding="utf-8"))["model_api_requests_performed"], 1
            )

    def test_seat_statement_301_to_900_is_accepted_but_outliers_diagnosed(self):
        ring = self.model["rings"][0]
        item = fake_ring(1, ring["member_ids"])
        item["seat_assessments"][0]["observation"] = "x" * 450
        _validate_seats(item, self.members, ring, {"card-0"})
        item["seat_assessments"][0]["observation"] = "PRIVATE-EXCERPT-" + "x" * 900
        with self.assertRaisesRegex(
            CouncilModelError, "field=observation, chars=916"
        ) as caught:
            _validate_seats(item, self.members, ring, {"card-0"})
        self.assertNotIn("PRIVATE-EXCERPT", str(caught.exception))

    def test_reuses_existing_paid_probe_and_checkpoints_all_nine_analyses(self):
        original = self.model
        question = self.question
        def sender(model, instruction, text, schema, api_key, max_output_tokens):
            data = json.loads(text)
            self.assertEqual(model, "gpt-6-luna")
            self.assertEqual(api_key, "mock-key")
            if schema is RING_SCHEMA:
                return fake_ring(
                    data["ring_id"],
                    [x["member_id"] for x in data["eight_distinct_roles"]]
                ), {"input_tokens": 100, "output_tokens": 300,
                    "total_tokens": 400}, "reply-ring-" + str(data["ring_id"])
            return fake_founders(
                [x["member_id"] for x in data["eight_founders"]]
            ), {"input_tokens": 500, "output_tokens": 300,
                "total_tokens": 800}, "reply-founders"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_file = root / "already-paid-probe.json"
            state_dir = root / "checkpoints"
            with patch.dict(os.environ, {
                "KLONE_COUNCIL72_PROBE_APPROVAL": "HYVAKSY_1_GPT_KUTSU"
            }):
                probe = run_council(
                    question, self.dossier, probe=True,
                    owner_confirms_public=True, api_key="mock-key",
                    network_sender=sender
                )
            seed_file.write_text(
                json.dumps(probe, ensure_ascii=False), encoding="utf-8"
            )
            calls = []
            def counted(*args):
                calls.append(args)
                return sender(*args)

            with patch.dict(os.environ, {
                "KLONE_COUNCIL72_RESUME_APPROVAL": "HYVAKSY_ENINTAAN_8_GPT_KUTSUA",
                "KLONE_COUNCIL72_API_APPROVAL": ""
            }):
                result = run_council(
                    question, self.dossier, live=True,
                    owner_confirms_public=True, api_key="mock-key",
                    seed_probe=seed_file, checkpoint_dir=state_dir,
                    network_sender=counted
                )
                self.assertEqual(len(calls), 8)
                self.assertEqual(result["model_api_requests_performed"], 8)
                self.assertEqual(result["model_api_requests_reused"], 1)
                self.assertEqual(result["model_analyses_total"], 9)
                self.assertEqual(
                    result["ring_calls"][0], probe["ring_calls"][0]
                )
                self.assertEqual(
                    len(list(state_dir.glob("*-accepted.json"))), 9
                )
                self.assertEqual(
                    len(list(state_dir.glob("*-received-unverified.json"))), 8
                )
                self.assertEqual(result["founder_synthesis"]["decision"],
                                 "owner_review_required")

                with patch(
                    "klone.council72_intelligence_bridge._network_response",
                    side_effect=AssertionError("re-run tried to bill")
                ):
                    again = run_council(
                        question, self.dossier, live=True,
                        owner_confirms_public=True, api_key="mock-key",
                        seed_probe=seed_file, checkpoint_dir=state_dir
                    )
                self.assertEqual(again["model_api_requests_performed"], 0)
                self.assertEqual(again["model_api_requests_reused"], 9)
                self.assertEqual(again["ring_calls"], result["ring_calls"])

    def test_invalid_paid_ring_response_saved_unverified_and_never_rebilled(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "state"
            calls = []
            def sender(model, instruction, text, schema, api_key, max_tokens):
                data = json.loads(text)
                calls.append(data["ring_id"])
                answer = fake_ring(data["ring_id"], [
                    x["member_id"] for x in data["eight_distinct_roles"]
                ])
                if data["ring_id"] == 2:
                    answer["seat_assessments"][0]["challenge"] = "X" * 910
                return answer, {
                    "input_tokens": 200, "output_tokens": 300,
                    "total_tokens": 500
                }, "response" + str(data["ring_id"])

            with patch.dict(os.environ, {
                "KLONE_COUNCIL72_API_APPROVAL": API_APPROVAL
            }):
                with self.assertRaisesRegex(
                    CouncilModelError, "ring 2: invalid seat statement"
                ):
                    run_council(
                        self.question, self.dossier, live=True,
                        owner_confirms_public=True, api_key="mock-key",
                        checkpoint_dir=directory, network_sender=sender
                    )
                self.assertEqual(calls, [1, 2])
                self.assertTrue((directory / "ring-01-accepted.json").exists())
                self.assertTrue((directory / "ring-02-received-unverified.json").exists())
                self.assertFalse((directory / "ring-02-accepted.json").exists())
                with patch(
                    "klone.council72_intelligence_bridge._network_response",
                    side_effect=AssertionError("unsafe automatic replay")
                ):
                    with self.assertRaisesRegex(CouncilModelError, "ring 2"):
                        run_council(
                            self.question, self.dossier, live=True,
                            owner_confirms_public=True, api_key="mock-key",
                            checkpoint_dir=directory
                        )

    def test_seed_or_evidence_tampering_blocks_before_any_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fake = {
                "kind": "klone-council72-intelligence-bridge-v1",
                "schema_version": 1, "mode": "api_one_ring_probe_completed",
                "model": "gpt-6-luna",
                "model_api_requests_performed": 1,
                "planned_api_requests": 1,
                "catalog_sha256": _fingerprint(self.model),
                "e11_11_report_sha256": self.dossier["report_sha256"],
                "question": self.question,
                "ring_calls": [],
                "owner_review_required": True,
                "scientific_truth_verified": False,
                "memory_write": False,
                "council_binding_votes": 0,
            }
            fake["report_sha256"] = _fingerprint(fake)
            path = directory / "fake-probe.json"
            path.write_text(json.dumps(fake))
            with patch.dict(os.environ, {
                "KLONE_COUNCIL72_RESUME_APPROVAL": "HYVAKSY_ENINTAAN_8_GPT_KUTSUA"
            }):
                with self.assertRaisesRegex(CouncilModelError, "probe seed"):
                    run_council(
                        self.question, self.dossier, live=True,
                        owner_confirms_public=True, api_key="mock-key",
                        seed_probe=path, checkpoint_dir=directory / "empty"
                    )
            self.assertFalse((directory / "empty").exists())

    def test_resume_requires_eight_call_authorization_not_old_nine(self):
        with patch.dict(os.environ, {
            "KLONE_COUNCIL72_API_APPROVAL": API_APPROVAL,
            "KLONE_COUNCIL72_RESUME_APPROVAL": ""
        }):
            with self.assertRaisesRegex(PermissionError, "at-most-eight"):
                run_council(
                    self.question, self.dossier, live=True,
                    owner_confirms_public=True, api_key="mock-key",
                    seed_probe="nonexistent.json",
                    checkpoint_dir="unused-checkpoints"
                )

    def test_local_checkpoint_tampering_blocks_network_before_any_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            ring = self.model["rings"][0]
            from klone import council72_intelligence_bridge as bridge
            data = bridge._checkpoint_doc(
                "ring-01", "accepted",
                bridge._checkpoint_context(
                    self.dossier, self.model, self.question, "gpt-6-luna"
                ),
                {
                    "ring_id": 1,
                    "eight_seat_assessments": fake_ring(1, ring["member_ids"]),
                    "api_response_id": "mock",
                    "usage": {
                        "input_tokens": 10, "output_tokens": 20,
                        "total_tokens": 30,
                    },
                    "request_sha256": "0" * 64,
                    "response_sha256": "1" * 64,
                    "model_generated_not_verified": True,
                }
            )
            state.mkdir()
            file = state / "ring-01-accepted.json"
            file.write_text(json.dumps(data), encoding="utf-8")
            # Even if the JSON file itself is parseable, its contents are not
            # eligible for replay without its original report fingerprint.
            data["payload"]["api_response_id"] = "forged"
            file.write_text(json.dumps(data), encoding="utf-8")
            with patch.dict(os.environ, {
                "KLONE_COUNCIL72_API_APPROVAL": API_APPROVAL
            }):
                with patch(
                    "klone.council72_intelligence_bridge._network_response",
                    side_effect=AssertionError("checkpoint bypassed")
                ):
                    with self.assertRaisesRegex(
                        CouncilModelError, "checkpoint ring-01 identity"
                    ):
                        run_council(
                            self.question, self.dossier, live=True,
                            owner_confirms_public=True, api_key="mock-key",
                            checkpoint_dir=state
                        )

    def test_founder_payload_is_bounded_even_for_very_long_accepted_ring_notes(self):
        from klone.council72_intelligence_bridge import (
            _founder_prompt, MAX_REQUEST_BYTES
        )
        inputs = []
        for ring in self.model["rings"][:8]:
            value = fake_ring(ring["id"], ring["member_ids"])
            for seat in value["seat_assessments"]:
                seat["observation"] = "x" * 900
                seat["challenge"] = "y" * 900
            for key in ("findings", "counterarguments", "open_questions"):
                value[key] = ["z" * 900] * 8
            inputs.append(value)
        instruction, payload = _founder_prompt(
            self.question, [], inputs, self.model, self.members
        )
        data = json.loads(payload)
        self.assertEqual(len(data["ring_analyses_unverified"]), 8)
        self.assertEqual(sum(len(x["seat_observations"]) for x in
                             data["ring_analyses_unverified"]), 64)
        self.assertTrue(all(
            len(seat["observation"]) <= 180
            for ring in data["ring_analyses_unverified"]
            for seat in ring["seat_observations"]
        ))
        self.assertLess(
            len(json.dumps({
                "model": "gpt-6-luna", "instructions": instruction,
                "input": [{"role": "user", "content": payload}],
                "max_output_tokens": 3400, "tools": [], "store": False
            }).encode("utf-8")),
            MAX_REQUEST_BYTES
        )

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
