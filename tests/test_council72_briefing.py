from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from klone.acceptance_matrix import DOMAINS
from klone.council72 import AUTHORITY, catalog
from klone.council72_briefing import briefing_replays, build_briefing, main, work_check_catalog
from klone.council72_review import review_session
from klone.council72_session import demo_session, run_session
from klone.main import create_app


class BriefingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = review_session(run_session(demo_session()))
        cls.report = build_briefing(cls.review)

    def test_replay_preserves_original_and_never_exposes_authority(self):
        original = deepcopy(self.review)
        report = build_briefing(self.review)
        self.assertEqual(report, self.report)
        self.assertTrue(briefing_replays(report))
        self.assertEqual(self.review, original)
        self.assertEqual(report["review"], original)
        self.assertTrue(all(report[k] is False for k in AUTHORITY))
        self.assertFalse(report["consolidation"]["memory_write_enabled"])
        self.assertIsNone(report["collective"]["common_goal_achieved"])

    def test_all_seventy_two_roles_and_eight_routes_come_from_real_catalog(self):
        model = catalog()
        founders = self.report["founders"]
        member_ids = [m["id"] for f in founders for m in f["members"]]
        self.assertEqual(len(member_ids), 64)
        self.assertEqual(set(member_ids) | {f["founder_id"] for f in founders}, set(range(1, 73)))
        for f in founders:
            king = next(m for m in model["members"] if m["id"] == f["founder_id"])
            courier = next(m for m in model["members"] if m["id"] == f["courier_id"])
            self.assertEqual(king["stewards_ring"], f["ring"])
            self.assertEqual(courier["courier_for"], king["id"])
            self.assertEqual([m["id"] for m in f["members"]], model["rings"][f["ring"] - 1]["member_ids"])
        limbo = founders[0]["members"]
        self.assertEqual(sorted(m["signal_ring"] for m in limbo), list(range(1, 9)))

    def test_consolidation_retains_superseded_sources_and_only_latest_claim_is_active(self):
        claims = self.report["consolidation"]["claims"]
        claim = next(c for c in claims if c["claim_key"] == "ring-2-ready")
        self.assertIn("new-threat", claim["history_observation_ids"])
        self.assertNotIn("new-threat", claim["active_observation_ids"])
        self.assertIn("corrected-threat", claim["supports"])
        self.assertEqual(claim["epistemic_status"], "reported_support")
        self.assertFalse(claim["truth_verified"])
        self.assertEqual(self.report["consolidation"]["corrections"],
            [{"superseded_id": "new-threat", "replacement_id": "corrected-threat"}])
        self.assertEqual(self.report["consolidation"]["history_observation_count"], 18)
        self.assertEqual(self.report["consolidation"]["active_observation_count"], 17)

    def test_cross_ring_conflict_is_visible_in_both_founder_briefings(self):
        request = demo_session()
        request["steps"] = request["steps"][:1]
        a, b = request["steps"][0]["observations"][0], request["steps"][0]["observations"][2]
        a["claim_key"] = b["claim_key"] = "shared-claim"
        b["stance"] = "contradicts"
        report = build_briefing(review_session(run_session(request)))
        for f in report["founders"][:2]:
            self.assertIn("shared-claim", f["conflict_claim_keys"])
            c = next(c for c in f["claims"] if c["claim_key"] == "shared-claim")
            self.assertEqual(c["epistemic_status"], "contested")
        self.assertEqual(report["collective"]["review_status"], "contradictory_evidence")

    def test_unknown_and_opposition_do_not_become_verified_support(self):
        for stance, expected in (("unknown", "mixed_unknown"), ("contradicts", "contested")):
            request = demo_session()
            request["steps"] = request["steps"][:1]
            request["steps"][0]["observations"][0]["stance"] = stance
            report = build_briefing(review_session(run_session(request)))
            claim = next(c for c in report["consolidation"]["claims"] if c["ring"] == 1)
            self.assertEqual(claim["epistemic_status"], expected)
            self.assertFalse(claim["truth_verified"])
            if stance == "unknown":
                self.assertEqual(report["founders"][0]["unknown_observation_ids"], ["r1-s1"])

    def test_all_unknown_and_all_opposition_remain_distinct(self):
        for stance, expected in (("unknown", "unexamined"), ("contradicts", "reported_opposition")):
            request = demo_session()
            request["steps"] = request["steps"][:1]
            for o in request["steps"][0]["observations"]:
                o["stance"] = stance
            report = build_briefing(review_session(run_session(request)))
            self.assertTrue(all(c["epistemic_status"] == expected for c in report["consolidation"]["claims"]))

    def test_founder_explicit_dissent_and_history_survive_synthesis(self):
        request = demo_session()
        votes = dict.fromkeys(map(str, catalog()["founder_ids"]), "endorse")
        votes["9"] = "oppose"
        request["steps"][-1]["founder_votes"] = votes
        report = build_briefing(review_session(run_session(request)))
        f = report["founders"][1]
        self.assertEqual(f["founder_vote"], "oppose")
        self.assertEqual([v["origin"] for v in f["vote_history"]], ["simulated", "simulated", "explicit_input"])
        self.assertIn(9, report["collective"]["minority_founder_ids"])
        self.assertEqual(report["collective"]["review_status"], "contested")

    def test_all_domain_files_and_exact_test_targets_exist_in_checkout(self):
        root = Path(__file__).parents[1]
        packets = self.report["domain_work_packets"]
        self.assertEqual({p["domain"] for p in packets}, set(DOMAINS))
        for p in packets:
            for name in p["related_files"]:
                self.assertTrue((root/name).is_file(), name)
            self.assertEqual(p["test_execution_status"], "not_run_by_briefing")
            self.assertIsNone(p["expected_commit"])
            self.assertFalse(p["execution_enabled"])
        media = next(p for p in packets if p["domain"] == "media")
        self.assertEqual(media["coverage"], "art_image_subset_only")
        ci = next(p for p in packets if p["domain"] == "ci")
        self.assertEqual(ci["test_targets"], [])
        self.assertIsNone(ci["commands_text"])

    def test_packaged_browser_command_allowlist_matches_python(self):
        path = Path(__file__).parents[1]/"src/klone/static/council72-work-checks.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), work_check_catalog())

    def test_selected_next_step_is_shortest_at_highest_selected_priority(self):
        tasks = [t for t in self.review["plan"]["tasks"] if t["allocation"] == "selected"]
        top = max(t["priority_score"] for t in tasks)
        eligible = [t for t in tasks if t["priority_score"] == top]
        expected = sorted(eligible, key=lambda t: (t["estimated_minutes"], t["id"]))[0]
        step = self.report["next_step"]
        self.assertEqual(step["task"], expected)
        self.assertIsNone(step["change_proposal"])
        self.assertTrue(step["open_questions"])

    def test_no_task_fits_means_no_next_step_and_manual_source_task_has_no_test_packet(self):
        report = build_briefing(review_session(self.review["session"], budget_minutes=1))
        self.assertIsNone(report["next_step"])
        request = demo_session()
        request["steps"] = request["steps"][:2]
        report = build_briefing(review_session(run_session(request)))
        self.assertEqual(report["next_step"]["task"]["kind"], "resolve_conflict")
        self.assertIsNone(report["next_step"]["work_packet"])

    def test_resource_totals_and_affect_deltas_match_retained_states(self):
        self.assertEqual(sum(f["allocated_minutes"] for f in self.report["founders"]),
                         self.review["plan"]["allocated_minutes"])
        for f in self.report["founders"]:
            state = self.review["session"]["member_state"][str(f["founder_id"])]
            self.assertEqual(f["affect"]["current"], state)
            for name, value in state.items():
                self.assertEqual(f["affect"]["delta"][name], round(value-f["affect"]["baseline"][name], 6))

    def test_partial_source_analysis_is_never_shown_as_complete(self):
        report = build_briefing(review_session(self.review["session"], max_source_groups=1))
        self.assertTrue(all(f["source_withdrawal_coverage_complete"] is False for f in report["founders"]))

    def test_historical_private_taint_cannot_be_laundered_by_claim_index(self):
        request = demo_session()
        request["steps"][1]["observations"][0]["classification"] = "sealed"
        request["steps"][2]["observations"][0]["classification"] = "sealed"
        report = build_briefing(review_session(run_session(request)))
        self.assertEqual(report["classification"], "sealed")
        self.assertTrue(all(c["classification"] == "sealed" for c in report["consolidation"]["claims"]))
        self.assertFalse(report["external_actions"])

    def test_untrusted_text_never_becomes_command_or_causes_io(self):
        request = demo_session()
        hostile = '$(touch /tmp/klone-evil); <img src=x onerror=alert(1)>'
        request["goal"] = hostile
        request["steps"][0]["observations"][0]["source_ref"] = hostile
        review = review_session(run_session(request))
        with patch("socket.create_connection", side_effect=AssertionError("network")), \
             patch("subprocess.Popen", side_effect=AssertionError("execution")), \
             patch.object(Path, "write_text", side_effect=AssertionError("write")):
            report = build_briefing(review)
        self.assertEqual(report["goal"], hostile)
        for p in report["domain_work_packets"]:
            self.assertNotIn("klone-evil", p["commands_text"] or "")

    def test_modified_derivatives_and_false_as_zero_cannot_replay(self):
        for field in ("source", "route", "command", "authority", "memory", "hash"):
            report = deepcopy(self.report)
            if field == "source": report["consolidation"]["claims"][0]["truth_verified"] = True
            elif field == "route": report["founders"][0]["courier_id"] = 27
            elif field == "command": report["domain_work_packets"][0]["commands_text"] = "echo evil"
            elif field == "authority": report["external_actions"] = 0
            elif field == "memory": report["consolidation"]["memory_write_enabled"] = True
            else: report["briefing_sha256"] = "0"*64
            self.assertFalse(briefing_replays(report), field)
        bad = deepcopy(self.review)
        bad["plan"]["execution_enabled"] = True
        with self.assertRaises(ValueError):
            build_briefing(bad)

    def test_cli_utf8_new_only_export_verify_and_original_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output = root/"review.json", root/"briefing.json"
            source.write_text(json.dumps(self.review, ensure_ascii=False), encoding="utf-8")
            before = source.read_bytes()
            self.assertEqual(main(["--input",str(source),"--output",str(output)]), 0)
            exported = output.read_bytes()
            self.assertTrue(briefing_replays(json.loads(exported)))
            with contextlib.redirect_stdout(io.StringIO()) as text:
                self.assertEqual(main(["--verify",str(output)]), 0)
            self.assertTrue(json.loads(text.getvalue())["replay_matches"])
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--input",str(source),"--output",str(output)])
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--verify",str(output),"--output",str(root/"no.json")])
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(output.read_bytes(), exported)
            runs = root/"runs"
            runs.mkdir()
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--demo","--runs-root",str(runs),"--output",str(runs/"blocked.json")])
            self.assertFalse((runs/"blocked.json").exists())


class BriefingApiTests(unittest.TestCase):
    def test_api_matches_offline_and_rejects_authority_and_partial_domains(self):
        client = TestClient(create_app())
        request = {"session": demo_session(), "budget_minutes": 30, "max_tasks": 2}
        response = client.post("/api/cognition/council72/briefing", json=request)
        self.assertEqual(response.status_code, 200)
        expected = build_briefing(review_session(run_session(request["session"]), budget_minutes=30, max_tasks=2))
        self.assertEqual(response.json(), expected)
        for changes in ({"execution_enabled": True}, {"budget_minutes": True}, {"domain_states": {"audit": "passed"}}):
            bad = client.post("/api/cognition/council72/briefing", json={**request, **changes})
            self.assertEqual(bad.status_code, 422)


if __name__ == "__main__":
    unittest.main()
