from copy import deepcopy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from klone.acceptance_matrix import DOMAINS
from klone.council72 import AUTHORITY
from klone.council72_briefing import build_briefing
from klone.council72_experiment import (FULL_COMMAND, build_contract, capture_identity, contract_replays,
    evaluate_contract, evaluation_matches_sources, main, validate_run_identity)
from klone.council72_review import review_session
from klone.council72_session import demo_session, run_session, validate_step
from klone.evidence_network import validate_run
from klone.evidence_run_context import collector_snapshot, context_id, digest, suite_snapshot
from klone.main import create_app
from forensics_fixture import create_run, save_packet
from run_context_fixture import environment, upgrade


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("experiment_battery", ROOT/"tools/termux_evidence_battery.py")
battery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(battery)


def selected_briefing(classification="public"):
    states = dict.fromkeys(DOMAINS, "passed")
    states["memory"] = "failed"
    request = demo_session()
    request["classification"] = classification
    return build_briefing(review_session(run_session(request), domain_states=states, budget_minutes=25))


class ExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.briefing = selected_briefing()
        cls.identity = {"commit":"a"*40,"test_suite_sha256":"c"*64,"collector_sha256":"d"*64,"platform":"linux"}
        cls.contract = build_contract(cls.briefing, "domain:memory", cls.identity,
                                      minimum_full_passed=3, maximum_full_skipped=1)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.runs = self.base/"runs"
        self.runs.mkdir()

    def make_run(self, status="passed", name="new"):
        directory = create_run(self.runs, name, status=status)
        data = upgrade(json.loads((directory/"run.json").read_text(encoding="utf-8")))
        data["environment"]["platform"] = "linux"
        data["execution"]["commands"]["full"] = [data["execution"]["python_executable"], *FULL_COMMAND]
        data["experiment_contract_sha256"] = self.contract["contract_sha256"]
        (directory/"syntax.log").write_text(json.dumps({"schema_version":1,"kind":"klone-syntax-check",
            "files":3,"status":"passed","errors":[]}), encoding="utf-8")
        self.save(directory, data)
        return directory, data

    def save(self, directory, data):
        data["execution"]["environment_after_sha256"] = digest(data["environment"])
        data["execution"]["comparison_id"] = context_id(data["environment"], data["execution"])
        (directory/"run.json").write_text(json.dumps(data), encoding="utf-8")
        save_packet(directory)

    def test_replay_fixes_criteria_and_retains_exact_task_route(self):
        original = deepcopy(self.briefing)
        self.assertTrue(contract_replays(self.contract))
        self.assertEqual(self.briefing, original)
        self.assertEqual(self.contract["route"], self.briefing["next_step"]["task"]["route"])
        for change in ("criteria", "task", "identity", "authority", "hash"):
            damaged = deepcopy(self.contract)
            if change == "criteria": damaged["acceptance"]["minimum_full_passed"] = 1
            elif change == "task": damaged["task_id"] = "domain:audit"
            elif change == "identity": damaged["expected"]["commit"] = "b"*40
            elif change == "authority": damaged["external_actions"] = 0
            else: damaged["contract_sha256"] = "0"*64
            self.assertFalse(contract_replays(damaged), change)

    def test_unselected_or_non_development_tasks_and_bad_limits_rejected(self):
        for task in ("domain:audit", "sensitivity:1", "$(publish)"):
            with self.subTest(task=task), self.assertRaises(ValueError):
                build_contract(self.briefing, task, self.identity)
        for kwargs in ({"minimum_full_passed":True}, {"minimum_full_passed":0},
                       {"maximum_full_skipped":-1}, {"maximum_full_skipped":1.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                build_contract(self.briefing, "domain:memory", self.identity, **kwargs)
        for change in ({"platform":"github_ci"}, {"commit":"x"*40}, {"extra":True}):
            with self.assertRaises(ValueError):
                build_contract(self.briefing,"domain:memory",{**self.identity,**change})

    def test_bound_originals_meet_criteria_and_remain_unchanged(self):
        directory, _ = self.make_run()
        before = {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in directory.iterdir()}
        report = evaluate_contract(self.contract, directory)
        self.assertEqual((report["binding_status"], report["outcome"]), ("matched","criteria_met"))
        self.assertEqual(report["observation"]["stance"], "supports")
        self.assertTrue(evaluation_matches_sources(report, directory))
        self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in directory.iterdir()})
        self.assertEqual(validate_step({"observations":[report["observation"]]})["observations"][0]["source_group"],
                         "klone-test-evidence")

    def test_repeated_runs_remain_one_source_group_without_duplicate_observation_ids(self):
        a,_ = self.make_run(name="a")
        b,_ = self.make_run(name="b")
        first, second = evaluate_contract(self.contract,a),evaluate_contract(self.contract,b)
        # Byte-identical evidence is the same observation even under another directory name.
        self.assertEqual(first["observation"]["source_group"], second["observation"]["source_group"])
        self.assertEqual(first["observation"]["id"], second["observation"]["id"])
        self.assertTrue(evaluation_matches_sources(first,b))
        self.assertFalse(first["provenance_authenticated"])

    def test_new_valid_contract_after_a_run_cannot_relabel_that_run(self):
        directory,_=self.make_run()
        changed=build_contract(self.briefing,"domain:memory",self.identity,
                               minimum_full_passed=1,maximum_full_skipped=100)
        self.assertTrue(contract_replays(changed))
        self.assertNotEqual(changed["contract_sha256"],self.contract["contract_sha256"])
        result=evaluate_contract(changed,directory)
        self.assertEqual(result["outcome"],"indeterminate")
        self.assertEqual(next(c["status"] for c in result["identity_checks"] if c["criterion"]=="contract_digest"),"failed")

    def test_truthful_failed_stage_and_threshold_failures_remain_failed(self):
        directory, data = self.make_run(status="failed")
        failed = evaluate_contract(self.contract, directory)
        self.assertEqual(failed["binding_status"], "matched")
        self.assertEqual(failed["outcome"], "criteria_failed")
        self.assertEqual(failed["observation"]["stance"], "contradicts")
        data["stages"]["full"].update(status="passed",exit_code=0)
        data.update(required_tests_passed=True,overall="passed")
        (directory/"full.log").write_text("2 passed, 2 skipped in 0.01s",encoding="utf-8")
        self.save(directory,data)
        thresholds = evaluate_contract(self.contract,directory)
        self.assertEqual(thresholds["outcome"], "criteria_failed")
        by_name={c["criterion"]:c["status"] for c in thresholds["acceptance_checks"]}
        self.assertEqual(by_name["minimum_full_passed"],"failed")
        self.assertEqual(by_name["maximum_full_skipped"],"failed")
        (directory/"full.log").write_text("3 passed, 1 deselected in 0.01s",encoding="utf-8")
        self.save(directory,data)
        self.assertEqual(evaluate_contract(self.contract,directory)["outcome"],"criteria_failed")

    def test_green_old_or_other_commit_platform_suite_collector_or_contract_is_indeterminate(self):
        for field in ("link", "commit", "platform", "suite", "collector", "command"):
            with self.subTest(field=field):
                directory,data=self.make_run(name=field)
                if field=="link": data.pop("experiment_contract_sha256")
                elif field=="commit": data["before"]["commit"]=data["after"]["commit"]="b"*40
                elif field=="platform": data["environment"]["platform"]="android"
                elif field=="suite": data["execution"]["test_suite_before"]["sha256"]=data["execution"]["test_suite_after"]["sha256"]="e"*64
                elif field=="collector": data["execution"]["collector_sha256"]=data["execution"]["collector_after_sha256"]="e"*64
                else: data["execution"]["commands"]["full"].append("tests/test_tiny.py")
                self.save(directory,data)
                report=evaluate_contract(self.contract,directory)
                self.assertNotEqual(report["binding_status"],"matched")
                self.assertEqual(report["outcome"],"indeterminate")
                self.assertEqual(report["observation"]["stance"],"unknown")

    def test_contradictory_green_manifest_or_mutated_packet_never_passes(self):
        directory,data=self.make_run()
        (directory/"full.log").write_text("1 failed, 3 passed in 0.01s",encoding="utf-8")
        self.save(directory,data)
        report=evaluate_contract(self.contract,directory)
        self.assertEqual(report["outcome"],"indeterminate")
        self.assertEqual(report["source"]["quality"],"contradictory")
        (directory/"full.log").write_text("3 passed in 0.01s",encoding="utf-8")
        report=evaluate_contract(self.contract,directory)
        self.assertEqual(report["outcome"],"indeterminate")

    def test_unknown_logs_legacy_and_incomplete_capture_stay_indeterminate(self):
        directory,data=self.make_run()
        (directory/"full.log").write_text("no recognized test summary",encoding="utf-8")
        self.save(directory,data)
        self.assertEqual(evaluate_contract(self.contract,directory)["outcome"],"indeterminate")
        legacy=create_run(self.runs,"legacy")
        self.assertEqual(evaluate_contract(self.contract,legacy)["outcome"],"indeterminate")
        data["stages"]["full"]["capture_complete"]=False
        data["collection_complete"]=False
        data["overall"]="failed"
        self.save(directory,data)
        self.assertEqual(evaluate_contract(self.contract,directory)["outcome"],"indeterminate")

    def test_empty_or_malformed_directory_has_unknown_result(self):
        directory=self.runs/"empty"
        directory.mkdir()
        report=evaluate_contract(self.contract,directory)
        self.assertEqual(report["outcome"],"indeterminate")
        (directory/"run.json").write_text('{"stages":null}',encoding="utf-8")
        self.assertEqual(evaluate_contract(self.contract,directory)["outcome"],"indeterminate")

    def test_browser_numeric_normalization_and_strict_boolean_authority(self):
        directory,_=self.make_run()
        original=evaluate_contract(self.contract,directory)
        def normalize(value):
            if isinstance(value,dict):return {k:normalize(v) for k,v in value.items()}
            if isinstance(value,list):return [normalize(v) for v in value]
            return int(value) if type(value) is float and value.is_integer() else value
        browser=normalize(self.contract)
        self.assertTrue(contract_replays(browser))
        self.assertEqual(evaluate_contract(browser,directory),original)
        original["provenance_authenticated"]=0
        self.assertFalse(evaluation_matches_sources(original,directory))

    def test_sealed_classification_and_no_network_or_claim_execution(self):
        directory,_=self.make_run()
        private=build_contract(selected_briefing("sealed"),"domain:memory",self.identity)
        with patch("socket.create_connection",side_effect=AssertionError("no network")), \
             patch("subprocess.run",side_effect=AssertionError("evaluation executes no commands")):
            result=evaluate_contract(private,directory)
        self.assertEqual(result["classification"],"sealed")
        self.assertEqual(result["observation"]["classification"],"sealed")
        for key in AUTHORITY:self.assertIs(result[key],False)

    def test_cli_exports_are_new_only_and_verification_requires_originals(self):
        directory,_=self.make_run()
        contract_file,output=self.base/"contract.json",self.base/"result.json"
        contract_file.write_text(json.dumps(self.contract,ensure_ascii=False),encoding="utf-8")
        args=["--evaluate-contract",str(contract_file),"--run-dir",str(directory),"--output",str(output)]
        self.assertEqual(main(args),0)
        original=output.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--verify-evaluation",str(output),"--run-dir",str(directory)]),0)
        for invalid in (args,["--verify-evaluation",str(output)],
            ["--evaluate-contract",str(contract_file),"--run-dir",str(directory),"--output",str(directory/"new.json")]):
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):main(invalid)
        self.assertEqual(output.read_bytes(),original)
        self.assertFalse((directory/"new.json").exists())
        (directory/"full.log").write_text("changed",encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            main(["--verify-evaluation",str(output),"--run-dir",str(directory)])

    def test_malformed_contract_cli_fails_cleanly_without_output_or_traceback(self):
        malformed=self.base/"bad.json"
        malformed.write_text('{}',encoding="utf-8")
        output=self.base/"never-created.json"
        with contextlib.redirect_stderr(io.StringIO()) as error,self.assertRaises(SystemExit):
            main(["--evaluate-contract",str(malformed),"--run-dir",str(self.runs),"--output",str(output)])
        self.assertNotIn("Traceback",error.getvalue())
        self.assertFalse(output.exists())

    def test_optional_contract_digest_is_strict_and_legacy_remains_valid(self):
        _,data=self.make_run()
        for bad in (True,0,None,"x"*64):
            changed=deepcopy(data);changed["experiment_contract_sha256"]=bad
            with self.assertRaises(ValueError):validate_run(changed)
        data.pop("experiment_contract_sha256")
        validate_run(data)


class CollectorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.briefing=selected_briefing()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/"checkout"
        for p in ("tests","src/klone","tools"):(self.root/p).mkdir(parents=True,exist_ok=True)
        for p in ("tests/test_toy.py","src/klone/evidence_run_context.py","tools/termux_evidence_battery.py"):
            (self.root/p).write_text("x=1\n",encoding="utf-8")
        self.python=Path(sys.executable)
        self.probe={"environment":{**environment(),"platform":"linux"},"executable":str(self.python),
                    "prefix":"/fixture","virtualenv_reported":True}
        self.identity={"commit":"a"*40,"test_suite_sha256":suite_snapshot(self.root)["sha256"],
                       "collector_sha256":collector_snapshot(self.root),"platform":"linux"}
        self.contract=build_contract(self.briefing,"domain:memory",self.identity)
        self.path=self.base/"contract.json";self.path.write_text(json.dumps(self.contract),encoding="utf-8")
        self.output=self.base/"new-run"

    def collect(self, *, commit="a"*40):
        seen=[]
        def stage(*args):
            self.assertTrue(self.path.is_file())
            seen.append(args[0])
            return {"status":"passed","exit_code":0,"capture_complete":True,"timed_out":False},b"3 passed in 0.01s"
        with patch.object(battery,"checkout",return_value={"commit":commit,"branch":"fixture","dirty":False}), \
             patch.object(battery,"probe_python",return_value=self.probe), \
             patch.object(battery,"run_stage",side_effect=stage):
            result=battery.run_battery(self.root,self.output,python=self.python,experiment_contract=self.path)
        return result,seen

    def test_contract_selected_before_any_stage_is_hashed_into_original_manifest(self):
        result,seen=self.collect()
        self.assertEqual(len(seen),4)
        self.assertEqual(result["experiment_contract_sha256"],self.contract["contract_sha256"])
        self.assertEqual(json.loads((self.output/"run.json").read_text(encoding="utf-8"))["experiment_contract_sha256"],self.contract["contract_sha256"])

    def test_wrong_commit_or_changed_suite_stops_before_stage_or_new_run_directory(self):
        with self.assertRaises(ValueError):self.collect(commit="b"*40)
        self.assertFalse(self.output.exists())
        (self.root/"tests/test_toy.py").write_text("x=2\n",encoding="utf-8")
        with self.assertRaises(ValueError):self.collect()
        self.assertFalse(self.output.exists())

    def test_capture_identity_rejects_dirty_checkout_before_hashing_or_tests(self):
        with patch("subprocess.check_output",return_value=b" M changed\n"):
            with self.assertRaisesRegex(ValueError,"clean checkout"):capture_identity(self.root)

    def test_runner_validation_rejects_forged_clean_claim_and_every_identity_mismatch(self):
        values=dict(commit=self.identity["commit"],suite_sha256=self.identity["test_suite_sha256"],
                    collector_sha256=self.identity["collector_sha256"],platform="linux",clean=True)
        for change in ({"clean":1},{"commit":"b"*40},{"collector_sha256":"e"*64},{"platform":"android"}):
            with self.assertRaises(ValueError):validate_run_identity(self.contract,**{**values,**change})


class ContractApiTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(create_app())
        states=dict.fromkeys(DOMAINS,"passed");states["memory"]="failed"
        self.request={"review":{"session":demo_session(),"domain_states":states,"budget_minutes":25},
            "task_id":"domain:memory","expected":{"commit":"a"*40,"test_suite_sha256":"c"*64,
                "collector_sha256":"d"*64,"platform":"android"}}

    def test_api_builds_replayable_contract_without_reading_paths(self):
        result=self.client.post("/api/cognition/council72/experiment-contract",json=self.request)
        self.assertEqual(result.status_code,200)
        self.assertTrue(contract_replays(result.json()))
        self.assertEqual(result.json()["expected"]["platform"],"android")

    def test_api_rejects_authority_paths_bad_platform_and_boolean_criteria(self):
        for change in ({"run_dir":"/private"},{"external_actions":True},{"minimum_full_passed":True},
                       {"expected":{**self.request["expected"],"platform":"github_ci"}},
                       {"task_id":"sensitivity:1"}):
            result=self.client.post("/api/cognition/council72/experiment-contract",json={**self.request,**change})
            self.assertEqual(result.status_code,422)


if __name__=="__main__":unittest.main()
