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
from klone.council72_review import DOMAIN_CHECKS, main, review_replays, review_session
from klone.council72_session import demo_session, run_session
from klone.main import create_app


class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session = run_session(demo_session())

    def first_request(self):
        request = demo_session()
        request["steps"] = request["steps"][:1]
        return request

    def test_deterministic_replay_and_original_history_preserved(self):
        original = deepcopy(self.session)
        report = review_session(self.session)
        self.assertEqual(report, review_session(self.session))
        self.assertTrue(review_replays(report))
        self.assertEqual(self.session, original)
        self.assertEqual(report["session"], original)
        self.assertFalse(report["source_analysis"]["history_rewritten"])
        self.assertEqual(report["source_analysis"]["status_sensitive_cases"], 2)

    def test_withdrawal_matches_independent_single_round_reconstruction(self):
        request = self.first_request()
        session = run_session(request)
        report = review_session(session)
        for case in report["source_analysis"]["cases"]:
            changed = deepcopy(request)
            changed["steps"][0]["observations"] = [o for o in changed["steps"][0]["observations"]
                if o["source_group"] != case["removed_source_group"]]
            direct = run_session(changed)
            self.assertEqual(case["review_status"], direct["rounds"][-1]["review_status"])
            self.assertEqual(case["missing_quorum_rings"], direct["rounds"][-1]["missing_quorum_rings"])
            original = {o["member_id"]: o["vote"] for o in session["latest_experiment"]["modulated"]["opinions"]}
            expected = sum(o["vote"] != original[o["member_id"]]
                           for o in direct["latest_experiment"]["modulated"]["opinions"])
            self.assertEqual(case["changed_member_votes"], expected)
            original_scores = {o["member_id"]: o["score"] for o in session["latest_experiment"]["modulated"]["opinions"]}
            scores = direct["latest_experiment"]["modulated"]["opinions"]
            self.assertEqual(case["mean_absolute_score_delta"],
                round(sum(abs(o["score"]-original_scores[o["member_id"]]) for o in scores)/72, 6))

    def test_only_active_corrections_enter_withdrawal_and_history_stays(self):
        report = review_session(self.session)
        removed = [n for case in report["source_analysis"]["cases"] for n in case["removed_observation_ids"]]
        self.assertIn("corrected-threat", removed)
        self.assertNotIn("new-threat", removed)
        self.assertEqual(report["session"]["request"]["steps"][1]["observations"][0]["id"], "new-threat")

    def test_empty_remaining_evidence_is_missing_not_endorsed(self):
        request = self.first_request()
        for row in request["steps"][0]["observations"]:
            row["source_group"] = "only-group"
        report = review_session(run_session(request))
        case = report["source_analysis"]["cases"][0]
        self.assertEqual(case["missing_quorum_rings"], list(range(1, 9)))
        self.assertEqual(case["review_status"], "insufficient_sources")

    def test_removing_conflicting_group_can_improve_hypothesis_without_authority(self):
        request = demo_session()
        request["steps"] = request["steps"][:2]
        report = review_session(run_session(request))
        case = next(c for c in report["source_analysis"]["cases"] if c["removed_source_group"] == "fixture-3")
        self.assertEqual(report["source_analysis"]["baseline_review_status"], "contradictory_evidence")
        self.assertEqual(case["review_status"], "endorsed_for_review")
        self.assertTrue(all(case[k] is False for k in AUTHORITY))
        conflicts = [t for t in report["plan"]["tasks"] if t["kind"] == "resolve_conflict"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["evidence_observation_ids"], ["new-threat", "r2-s1", "r2-s2"])

    def test_explicit_founder_opposition_is_preserved_in_every_case(self):
        request = self.first_request()
        votes = dict.fromkeys(map(str, catalog()["founder_ids"]), "endorse")
        votes["9"] = "oppose"
        request["steps"][0]["founder_votes"] = votes
        report = review_session(run_session(request))
        self.assertTrue(all(9 not in c["changed_founder_ids"] for c in report["source_analysis"]["cases"]))
        dissent = [t for t in report["plan"]["tasks"] if t["kind"] == "review_dissent"]
        self.assertEqual(dissent[0]["founder_vote"], "oppose")

    def test_unknown_remains_a_task_with_real_observation_references(self):
        request = self.first_request()
        request["steps"][0]["observations"][0]["stance"] = "unknown"
        report = review_session(run_session(request))
        task = next(t for t in report["plan"]["tasks"] if t["kind"] == "check_unknown")
        self.assertEqual(task["evidence_observation_ids"], ["r1-s1"])
        self.assertEqual(task["route"]["ring"], 1)
        self.assertEqual(report["source_analysis"]["baseline_review_status"], "insufficient_sources")

    def test_partial_coverage_lists_every_omitted_group(self):
        report = review_session(self.session, max_source_groups=1)
        analysis = report["source_analysis"]
        self.assertFalse(analysis["coverage_complete"])
        self.assertEqual(analysis["tested_source_groups"], ["fixture-1"])
        self.assertEqual(analysis["omitted_source_groups"], ["fixture-2", "fixture-3"])
        self.assertEqual(len(analysis["cases"]), 1)

    def test_task_count_and_minutes_are_hard_plan_limits_and_no_task_is_split(self):
        for budget, count in ((1, 8), (25, 1), (60, 2), (480, 32)):
            with self.subTest(budget=budget, count=count):
                report = review_session(self.session, budget_minutes=budget, max_tasks=count)
                plan = report["plan"]
                selected = [t for t in plan["tasks"] if t["allocation"] == "selected"]
                self.assertLessEqual(len(selected), count)
                self.assertEqual(sum(t["estimated_minutes"] for t in selected), plan["allocated_minutes"])
                self.assertLessEqual(plan["allocated_minutes"], budget)
                self.assertEqual(plan["remaining_minutes"], budget-plan["allocated_minutes"])
                if budget == 1:
                    self.assertFalse(selected)

    def test_failed_regression_precedes_sensitivity_and_default_unverified_is_explicit(self):
        states = dict.fromkeys(DOMAINS, "passed")
        states["audit"] = "failed"
        report = review_session(self.session, domain_states=states, budget_minutes=25)
        first = report["plan"]["tasks"][0]
        self.assertEqual((first["id"], first["allocation"]), ("domain:audit", "selected"))
        self.assertEqual(report["options"]["domain_states"], states)
        default = review_session(self.session)
        self.assertEqual(default["options"]["domain_states"], dict.fromkeys(DOMAINS, "unverified"))
        self.assertEqual(default["plan"]["domain_state_source"], "caller_declared_not_verified")

    def test_all_twelve_domains_have_catalog_bound_routes_and_honest_check_targets(self):
        report = review_session(self.session)
        tasks = [t for t in report["plan"]["tasks"] if t["kind"] == "development_check"]
        self.assertEqual({t["domain"] for t in tasks}, set(DOMAINS))
        model = catalog()
        for task in report["plan"]["tasks"]:
            route = task["route"]
            member = next(m for m in model["members"] if m["id"] == route["courier_id"])
            self.assertEqual(member["courier_for"], route["founder_id"])
            self.assertEqual(model["rings"][route["ring"]-1]["steward_id"], route["founder_id"])
        for target in DOMAIN_CHECKS.values():
            if target is not None:
                self.assertTrue((Path(__file__).parents[1]/target).is_file(), target)
        media = next(t for t in tasks if t["domain"] == "media")
        self.assertIsNone(media["check_target"])
        self.assertEqual(media["check_target_kind"], "unmapped")

    def test_bounds_types_and_incomplete_states_rejected(self):
        for kwargs in ({"budget_minutes":True}, {"budget_minutes":0}, {"budget_minutes":481},
                       {"max_tasks":33}, {"max_tasks":1.5}, {"max_source_groups":False},
                       {"max_source_groups":33}, {"domain_states":{"memory":"passed"}},
                       {"domain_states":dict.fromkeys(DOMAINS, True)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                review_session(self.session, **kwargs)

    def test_tampered_session_or_review_cannot_replay(self):
        damaged = deepcopy(self.session)
        damaged["member_state"]["9"]["dopamine"] = .01
        with self.assertRaises(ValueError):
            review_session(damaged)
        original = review_session(self.session)
        for field in ("task", "case", "authority", "options", "hash"):
            report = deepcopy(original)
            if field == "task": report["plan"]["tasks"][0]["execution_enabled"] = True
            elif field == "case": report["source_analysis"]["cases"][0]["review_status"] = "pending"
            elif field == "authority": report["external_actions"] = 0
            elif field == "options": report["options"]["budget_minutes"] = 1
            else: report["review_sha256"] = "0"*64
            self.assertFalse(review_replays(report), field)

    def test_private_classification_and_opaque_hostile_text_have_no_io_or_authority(self):
        request = self.first_request()
        request["steps"][0]["observations"][0].update(classification="sealed",
            summary="<script>publish()</script>", source_ref="$(touch /tmp/klone-do-not-execute)")
        session = run_session(request)
        with patch("socket.create_connection", side_effect=AssertionError("no network")), \
             patch.object(Path, "write_text", side_effect=AssertionError("no writes")):
            report = review_session(session)
        self.assertEqual(report["classification"], "sealed")
        self.assertTrue(all(report[k] is False for k in AUTHORITY))
        self.assertFalse(report["plan"]["execution_enabled"])
        self.assertTrue(all(t["execution_enabled"] is False for t in report["plan"]["tasks"]))

    def test_cli_utf8_verify_new_only_exports_and_source_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output = root/"session.json", root/"review.json"
            source.write_text(json.dumps(self.session, ensure_ascii=False), encoding="utf-8")
            before = source.read_bytes()
            args = ["--input",str(source),"--output",str(output),"--budget-minutes","30"]
            self.assertEqual(main(args), 0)
            exported = output.read_bytes()
            self.assertTrue(review_replays(json.loads(exported)))
            with contextlib.redirect_stdout(io.StringIO()) as checked:
                self.assertEqual(main(["--verify",str(output)]), 0)
            self.assertTrue(json.loads(checked.getvalue())["replay_matches"])
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(args)
            runs = root/"runs"
            runs.mkdir()
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--demo","--runs-root",str(runs),"--output",str(runs/"forbidden.json")])
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(output.read_bytes(), exported)
            self.assertFalse((runs/"forbidden.json").exists())


class ReviewApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_api_matches_cli_core_with_canonical_strict_request(self):
        request = {"session":demo_session(),"budget_minutes":30,"max_tasks":2}
        response = self.client.post("/api/cognition/council72/review", json=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), review_session(run_session(request["session"]), budget_minutes=30,max_tasks=2))
        self.assertTrue(review_replays(response.json()))

    def test_api_rejects_extra_authority_invalid_budgets_and_partial_domains(self):
        for changes in ({"budget_minutes":True}, {"budget_minutes":0}, {"budget_minutes":481},
                        {"max_tasks":33}, {"max_source_groups":0}, {"external_actions":True},
                        {"domain_states":{"audit":"passed"}}):
            response = self.client.post("/api/cognition/council72/review", json={"session":demo_session(),**changes})
            self.assertEqual(response.status_code, 422, changes)


if __name__ == "__main__":
    unittest.main()
