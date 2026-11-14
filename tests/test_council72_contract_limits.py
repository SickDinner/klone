from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from klone.council72_contract import contract_replays,lock_checkout,register_contract,template,validate_checkout
from klone.council72_evidence import evaluate_evidence
from klone.evidence_run_context import collector_snapshot,context_id,digest,suite_snapshot
from klone.main import create_app
from forensics_fixture import create_run,save_packet
from run_context_fixture import environment,upgrade

ROOT=Path(__file__).parents[1]
SPEC=importlib.util.spec_from_file_location("locked_contract_battery",ROOT/"tools/termux_evidence_battery.py")
battery=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(battery)


def locked_spec():
    spec=template("a"*40)
    spec["criteria"]=spec["criteria"][:1]
    spec["criteria"][0].update(platform="linux",min_passed=3,max_skipped=1,max_deselected=0,full_suite=True)
    spec["execution_identity"]={"test_suite_sha256":"c"*64,"collector_sha256":"d"*64}
    return spec


class ContractLimitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.runs=self.root/"runs";self.runs.mkdir()
        self.spec=locked_spec();self.contract=register_contract(self.spec)
        self.path=self.root/"contract.json";self.write_contract()

    def write_contract(self):
        self.path.write_text(json.dumps(self.contract,ensure_ascii=False),encoding="utf-8")

    def run_fixture(self,name="run",text="3 passed in 0.01s"):
        directory=create_run(self.runs,name)
        data=upgrade(json.loads((directory/"run.json").read_text(encoding="utf-8")))
        data["environment"]["platform"]="linux"
        data["execution"]["commands"]["full"]=[data["execution"]["python_executable"],"-B","-m","pytest","-p","no:cacheprovider","-q"]
        file_hash=hashlib.sha256(self.path.read_bytes()).hexdigest()
        data["execution"]["experiment_contract"]={"contract_sha256":self.contract["contract_sha256"],
            "file_sha256":file_hash,"after_file_sha256":file_hash}
        (directory/"full.log").write_text(text,encoding="utf-8")
        self.save(directory,data)
        return directory,data

    def save(self,directory,data):
        data["execution"]["environment_after_sha256"]=digest(data["environment"])
        data["execution"]["comparison_id"]=context_id(data["environment"],data["execution"])
        (directory/"run.json").write_text(json.dumps(data),encoding="utf-8");save_packet(directory)

    def report(self,*names):return evaluate_evidence(self.path,self.runs,list(names))

    def test_original_contract_remains_byte_protocol_compatible(self):
        self.assertEqual(register_contract(template("a"*40))["contract_sha256"],
            "d7201452342c73f1384a2b613136581ef0c733236d19eb33c343c1961a722b40")
        client=TestClient(create_app())
        self.assertEqual(client.post("/api/cognition/council72/contract",json=template("a"*40)).json(),
                         register_contract(template("a"*40)))

    def test_locked_fields_are_hashed_and_strictly_validated(self):
        self.assertTrue(contract_replays(self.contract))
        changed=deepcopy(self.contract);changed["spec"]["criteria"][0]["max_skipped"]=100
        self.assertFalse(contract_replays(changed))
        for change in ({"max_skipped":True},{"max_deselected":-1},{"full_suite":False},
                       {"platform":"android"},{"stage":"syntax","min_passed":0},
                       {"full_suite":True,"max_deselected":1}):
            spec=deepcopy(self.spec);spec["criteria"][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):register_contract(spec)
        spec=deepcopy(self.spec);spec["execution_identity"]["extra"]="x"
        with self.assertRaises(ValueError):register_contract(spec)

    def test_api_preserves_optional_fields_and_rejects_boolean_counts(self):
        client=TestClient(create_app())
        result=client.post("/api/cognition/council72/contract",json=self.spec)
        self.assertEqual(result.status_code,200);self.assertEqual(result.json(),self.contract)
        self.spec["criteria"][0]["max_skipped"]=True
        self.assertEqual(client.post("/api/cognition/council72/contract",json=self.spec).status_code,422)

    def test_complete_unfiltered_correct_identity_passes_without_source_writes(self):
        directory,_=self.run_fixture()
        before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in directory.iterdir()}
        report=self.report("run")
        self.assertEqual(report["status"],"met_for_review")
        self.assertFalse(report["test_execution_authenticated"])
        self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in directory.iterdir()})

    def test_passed_summary_with_too_many_skips_or_deselection_is_not_met(self):
        for name,text,reason in (("skips","3 passed, 2 skipped in 0.01s","reported_skips_above_locked_maximum"),
                                ("selected","3 passed, 1 deselected in 0.01s","reported_deselection_above_locked_maximum")):
            self.run_fixture(name,text)
            result=self.report(name)
            self.assertEqual(result["status"],"not_met")
            self.assertEqual(result["criteria"][0]["cases"][0]["reason"],reason)

    def test_changed_suite_collector_or_filtered_command_stays_unknown(self):
        for mode in ("suite","collector","command"):
            directory,data=self.run_fixture(mode)
            e=data["execution"]
            if mode=="suite":e["test_suite_before"]["sha256"]=e["test_suite_after"]["sha256"]="e"*64
            elif mode=="collector":e["collector_sha256"]=e["collector_after_sha256"]="e"*64
            else:e["commands"]["full"].append("tests/test_tiny.py")
            self.save(directory,data)
            result=self.report(mode)
            self.assertEqual(result["status"],"unknown")
            self.assertIn(result["criteria"][0]["cases"][0]["reason"],
                          ("different_locked_suite_or_collector","filtered_or_unrecognized_full_suite_command"))

    def test_linux_cannot_fill_locked_windows_criterion(self):
        self.spec["criteria"][0]["platform"]="win32"
        self.contract=register_contract(self.spec);self.write_contract();self.run_fixture()
        result=self.report("run")
        self.assertEqual(result["status"],"unknown")
        self.assertEqual(result["criteria"][0]["matching_runs"],0)

    def test_new_relaxed_contract_cannot_relabel_previously_bound_evidence(self):
        self.run_fixture(text="3 passed, 2 skipped in 0.01s")
        old=self.contract["contract_sha256"]
        self.spec["criteria"][0]["max_skipped"]=100
        self.contract=register_contract(self.spec);self.write_contract()
        self.assertNotEqual(self.contract["contract_sha256"],old)
        self.assertEqual(self.report("run")["status"],"unknown")

    def test_copied_evidence_does_not_create_new_observation_identity(self):
        directory,_=self.run_fixture();shutil.copytree(directory,self.runs/"copy")
        first=self.report("run")["session_step_proposals"][0]["observations"][0]
        for names in (("copy",),("run","copy")):
            other=self.report(*names)["session_step_proposals"][0]["observations"][0]
            self.assertEqual(first["id"],other["id"])
            self.assertEqual(other["source_group"],"local-artifact-claims")

    def test_unittest_summary_cannot_satisfy_locked_pytest_count_limits(self):
        self.run_fixture(text="Ran 3 tests in 0.01s\n\nOK\n")
        self.assertEqual(self.report("run")["status"],"unknown")


class LockedCollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/"checkout";self.root.mkdir()
        self.contract=register_contract(locked_spec())
        self.path=self.base/"contract.json";self.path.write_text(json.dumps(self.contract),encoding="utf-8")

    def test_identity_mismatch_stops_before_reserving_output_or_running_stage(self):
        out=self.base/"must-not-exist"
        with patch.object(battery,"checkout",return_value={"commit":"a"*40,"dirty":False}), \
             patch.object(battery,"probe_python",return_value={"environment":{**environment(),"platform":"linux"}}), \
             patch.object(battery,"suite_snapshot",return_value={"sha256":"e"*64,"file_count":1}), \
             patch.object(battery,"collector_digest",return_value="d"*64), \
             patch.object(battery,"run_stage",side_effect=AssertionError("must not execute")) as stage:
            with self.assertRaises(ValueError):battery.run_battery(self.root,out,python=Path(sys.executable),experiment_contract=self.path)
        stage.assert_not_called();self.assertFalse(out.exists())

    def test_dirty_platform_and_collector_mismatch_are_preflight_errors(self):
        values=dict(commit="a"*40,suite_sha256="c"*64,collector_sha256="d"*64,platform="linux",clean=True)
        validate_checkout(self.contract,**values)
        for change in ({"clean":1},{"platform":"win32"},{"collector_sha256":"e"*64}):
            with self.assertRaises(ValueError):validate_checkout(self.contract,**{**values,**change})

    def test_identity_is_captured_from_real_clean_checkout_and_dirty_is_rejected(self):
        for path in ("tests/test_toy.py","src/klone/evidence_run_context.py","tools/termux_evidence_battery.py"):
            target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text("x=1\n",encoding="utf-8")
        def git(*args):return subprocess.check_output(["git","-C",str(self.root),*args]).decode().strip()
        git("init","-q");git("add",".");git("-c","user.name=Test","-c","user.email=test@example.invalid","commit","-qm","fixture")
        spec=locked_spec();spec.pop("execution_identity");spec["target_commit"]=git("rev-parse","HEAD")
        contract=lock_checkout(spec,self.root)
        self.assertEqual(contract["spec"]["execution_identity"],{"test_suite_sha256":suite_snapshot(self.root)["sha256"],"collector_sha256":collector_snapshot(self.root)})
        self.assertEqual(battery.collector_digest(self.root),collector_snapshot(self.root))
        (self.root/"tests/test_toy.py").write_text("x=2\n",encoding="utf-8")
        with self.assertRaises(ValueError):lock_checkout(spec,self.root)


if __name__=="__main__":unittest.main()
