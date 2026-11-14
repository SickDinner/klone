from copy import deepcopy
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from klone.council72 import AUTHORITY
from klone.council72_contract import contract_replays, load_contract, main as contract_main, register_contract, template
from klone.council72_evidence import evaluate_evidence, main
from klone.council72_session import validate_step
from klone.evidence_network import build_packet, canonical, validate_run
from klone.evidence_run_context import context_id, digest
from klone.main import create_app
from forensics_fixture import create_run, save_packet
from run_context_fixture import upgrade

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("council_contract_battery", ROOT/"tools/termux_evidence_battery.py")
battery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(battery)


class ContractTests(unittest.TestCase):
    def test_deterministic_explicit_criteria_and_no_authority(self):
        spec = template("a"*40)
        report = register_contract(spec)
        self.assertEqual(report, register_contract(spec))
        self.assertTrue(contract_replays(report))
        self.assertTrue(all(report[k] is False for k in AUTHORITY))
        self.assertFalse(report["registration_time_authenticated"])
        changed = deepcopy(report)
        changed["spec"]["criteria"][0]["min_passed"] = 0
        self.assertFalse(contract_replays(changed))
        changed = deepcopy(report)
        changed["external_actions"] = 0
        self.assertFalse(contract_replays(changed))

    def test_bounds_duplicate_claims_extra_fields_and_types_rejected(self):
        mutations = [lambda s:s.update(target_commit="main"), lambda s:s.update(criteria=[]),
            lambda s:s.update(criteria=s["criteria"]*9), lambda s:s.update(external_actions=True),
            lambda s:s["criteria"][0].update(min_passed=True), lambda s:s["criteria"][0].update(domain="missing"),
            lambda s:s["criteria"][0].update(stage="torch_probe"), lambda s:s["criteria"][0].update(environment="ci"),
            lambda s:s["criteria"][1].update(claim_key=s["criteria"][0]["claim_key"]),
            lambda s:s["criteria"][0].update(stage="syntax",min_passed=1)]
        for mutation in mutations:
            spec = template("a"*40); mutation(spec)
            with self.subTest(spec=spec), self.assertRaises(ValueError):register_contract(spec)

    def test_api_registers_without_filesystem_or_extra_authority(self):
        client = TestClient(create_app())
        spec = template("a"*40)
        response = client.post("/api/cognition/council72/contract",json=spec)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),register_contract(spec))
        self.assertEqual(client.post("/api/cognition/council72/contract",json={**spec,"run_directory":"/"}).status_code,422)

    def test_contract_cli_keeps_first_registration_and_checks_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/"contract.json"
            args=["--template","--commit","a"*40,"--output",str(output)]
            self.assertEqual(contract_main(args),0)
            before=output.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(contract_main(["--verify",str(output)]),0)
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):contract_main(args)
            self.assertEqual(before,output.read_bytes())


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name);self.runs = self.root/"runs";self.runs.mkdir()
        self.contract = register_contract(template("a"*40));self.path = self.root/"contract.json"
        self.path.write_text(json.dumps(self.contract,ensure_ascii=False),encoding="utf-8")

    def run_fixture(self,name="work",platform="linux",status="passed",binding=True):
        directory = create_run(self.runs,name,status=status)
        data = upgrade(json.loads((directory/"run.json").read_text(encoding="utf-8")))
        data["environment"]["platform"] = platform
        execution = data["execution"]
        execution["environment_after_sha256"] = digest(data["environment"])
        if binding:
            file_hash = hashlib.sha256(self.path.read_bytes()).hexdigest()
            execution["experiment_contract"] = {"contract_sha256":self.contract["contract_sha256"],"file_sha256":file_hash,"after_file_sha256":file_hash}
        execution["comparison_id"] = context_id(data["environment"],execution)
        (directory/"run.json").write_text(json.dumps(data),encoding="utf-8");save_packet(directory)
        return directory,data

    def report(self,*names,**kwargs):return evaluate_evidence(self.path,self.runs,list(names),**kwargs)

    def save(self,directory,data):
        (directory/"run.json").write_text(json.dumps(data),encoding="utf-8");save_packet(directory)

    def test_work_pass_never_supplies_missing_android_and_groups_are_conservative(self):
        self.run_fixture()
        report = self.report("work")
        results = {r["criterion"]["environment"]:r["status"] for r in report["criteria"]}
        self.assertEqual(results,{"work":"met_for_review","android":"unknown"})
        self.assertEqual(report["status"],"unknown")
        step = validate_step(report["session_step_proposals"][0])
        self.assertEqual({o["source_group"] for o in step["observations"]},{"local-artifact-claims"})
        self.assertEqual(report["classification"],"restricted")
        self.assertEqual(report["runs"][0]["github"]["state"],"unavailable")
        self.assertFalse(report["deployment_approval"])

    def test_both_reported_environments_pass_with_no_execution_authentication(self):
        self.run_fixture();self.run_fixture("android","android")
        report = self.report("work","android")
        self.assertEqual(report["status"],"met_for_review")
        self.assertFalse(report["test_execution_authenticated"])
        self.assertFalse(report["registration_time_authenticated"])

    def test_signature_is_a_separate_witness_result_not_execution_proof(self):
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        except ImportError:
            self.skipTest("optional signature backend unavailable")
        from klone.evidence_attestation import sign
        directory,_=self.run_fixture()
        private=bytes(range(32));key=Ed25519PrivateKey.from_private_bytes(private)
        packet=json.loads((directory/"evidence-packet.json").read_text(encoding="utf-8"))
        report=self.report("work",attestations={"work":sign(packet,"test-witness",private)},
                           trusted_keys={"test-witness":key.public_key().public_bytes_raw().hex()})
        self.assertTrue(report["runs"][0]["attestation"]["witness_authenticated"])
        self.assertFalse(report["test_execution_authenticated"])
        self.assertFalse(report["deployment_approval"])

    def test_one_consistent_failure_falsifies_all_selected_matching_runs_rule(self):
        self.run_fixture();self.run_fixture("failed","linux","failed")
        report = self.report("work","failed")
        work = next(r for r in report["criteria"] if r["criterion"]["environment"]=="work")
        self.assertEqual(work["status"],"not_met")
        self.assertEqual(report["status"],"not_met")

    def test_legacy_missing_packet_empty_log_and_wrong_binding_remain_unknown(self):
        for mode in ("legacy","no-packet","empty","binding","unbound","dirty","wrong-commit"):
            with self.subTest(mode=mode):
                directory,data = self.run_fixture(mode,binding=mode!="unbound")
                if mode=="legacy":
                    directory2=create_run(self.runs,"legacy-v1");name=directory2.name
                else:
                    name=mode
                    if mode=="no-packet":(directory/"evidence-packet.json").unlink()
                    elif mode=="empty":(directory/"full.log").write_bytes(b"");save_packet(directory)
                    elif mode=="binding":data["execution"]["experiment_contract"]["contract_sha256"]="b"*64;data["execution"]["comparison_id"]=context_id(data["environment"],data["execution"]);self.save(directory,data)
                    elif mode=="dirty":data["before"]["dirty"]=True;data["checkout_consistent"]=False;data["overall"]="failed";self.save(directory,data)
                    elif mode=="wrong-commit":data["before"]["commit"]=data["after"]["commit"]="b"*40;self.save(directory,data)
                report=self.report(name)
                self.assertTrue(all(r["status"]=="unknown" for r in report["criteria"]))

    def test_bound_contract_changes_and_incomplete_capture_are_not_accepted(self):
        for mode in ("changed","incomplete"):
            directory,data=self.run_fixture(mode)
            e=data["execution"]
            if mode=="changed":e["experiment_contract"]["after_file_sha256"]="0"*64;e["context_consistent"]=False
            else:data["stages"]["full"]["capture_complete"]=False;data["collection_complete"]=False
            data["overall"]="failed";self.save(directory,data)
            self.assertEqual(self.report(mode)["status"],"unknown")

    def test_contradictory_log_cannot_be_counted_as_a_confirmed_failure(self):
        directory,_=self.run_fixture()
        (directory/"full.log").write_text("1 failed in 0.04s",encoding="utf-8");save_packet(directory)
        work=next(r for r in self.report("work")["criteria"] if r["criterion"]["environment"]=="work")
        self.assertEqual(work["status"],"unknown")
        self.assertEqual(work["cases"][0]["reason"],"contradictory_evidence")

    def test_unknown_scope_poisoning_and_locked_minimum(self):
        self.run_fixture();broken=self.runs/"broken";broken.mkdir();(broken/"run.json").write_text("{",encoding="utf-8")
        work=next(r for r in self.report("work","broken")["criteria"] if r["criterion"]["environment"]=="work")
        self.assertEqual(work["status"],"unknown")
        spec=template("a"*40);spec["criteria"][0]["min_passed"]=4
        self.contract=register_contract(spec);self.path.write_text(json.dumps(self.contract),encoding="utf-8")
        self.run_fixture("minimum")
        self.assertEqual(self.report("minimum")["status"],"not_met")

    def test_path_bounds_symlinks_hostile_logs_and_originals_preserved(self):
        directory,_=self.run_fixture()
        (directory/"full.log").write_text('$(touch /tmp/evil)\n3 passed in 0.04s',encoding="utf-8");save_packet(directory)
        before={str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in self.runs.rglob('*') if p.is_file()}
        with patch('subprocess.Popen',side_effect=AssertionError('no commands')),patch('socket.create_connection',side_effect=AssertionError('no network')):
            first=self.report("work");self.assertEqual(first,self.report("work"))
        self.assertEqual(before,{str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in self.runs.rglob('*') if p.is_file()})
        for names in ([],["../work"],["work","work"],["work"]*9):
            with self.assertRaises(ValueError):evaluate_evidence(self.path,self.runs,names)
        link=self.runs/"link"
        try:link.symlink_to(directory,target_is_directory=True)
        except OSError:return
        with self.assertRaises(ValueError):self.report("link")

    def test_cli_exports_new_report_and_rechecks_original_sources(self):
        self.run_fixture();output=self.root/"review.json"
        args=["--contract",str(self.path),"--runs-root",str(self.runs),"--run","work"]
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main([*args,"--output",str(output)]),0)
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main([*args,"--verify",str(output)]),0)
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):main([*args,"--output",str(output)])
        (self.runs/"work/full.log").write_text('4 passed in 0.04s',encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):main([*args,"--verify",str(output)])


class CollectorContractTests(unittest.TestCase):
    def setUp(self):
        EvidenceTests.setUp(self)

    def collect(self,change=None):
        root=self.root/"checkout";root.mkdir();out=self.runs/"captured"
        python=Path(sys.executable)
        commands={n:[str(python),'-B','stub'] for n in ('syntax','cognition','full','local_deploy')};commands['torch_probe']=None
        calls=[]
        def stage(*args):
            calls.append(args)
            if change and len(calls)==1:change()
            return {"exit_code":0,"status":"passed","capture_complete":True,"timed_out":False},b'3 passed in 0.04s'
        from run_context_fixture import environment
        with patch.object(battery,'checkout',return_value={"commit":"a"*40,"branch":"test","dirty":False}),patch.object(battery,'probe_python',return_value={"environment":environment(),"prefix":"/test"}),patch.object(battery,'suite_snapshot',return_value={"sha256":"c"*64,"file_count":1}),patch.object(battery,'collector_digest',return_value="d"*64),patch.object(battery,'stage_commands',return_value=commands),patch.object(battery,'run_stage',side_effect=stage):
            return battery.run_battery(root,out,python=python,experiment_contract=self.path)

    def test_collector_reads_contract_before_and_after_actual_stage_calls(self):
        report=self.collect()
        self.assertEqual(report["execution"]["experiment_contract"]["contract_sha256"],self.contract["contract_sha256"])
        self.assertTrue(report["execution"]["context_consistent"])
        validate_run(report)

    def test_collector_detects_contract_mutation_during_stages(self):
        report=self.collect(lambda:self.path.write_text('{}',encoding='utf-8'))
        self.assertFalse(report["execution"]["context_consistent"])
        self.assertEqual(report["overall"],"failed")
        validate_run(report)

    def test_collector_preserves_run_and_blocks_acceptance_when_contract_disappears(self):
        report=self.collect(self.path.unlink)
        self.assertEqual(report["overall"],"failed")
        self.assertIsNone(report["execution"]["experiment_contract"]["after_file_sha256"])
        self.assertTrue((self.runs/"captured/run.json").is_file())
        validate_run(report)

    def test_wrong_target_stops_before_any_stage_or_output(self):
        root=self.root/"checkout";root.mkdir()
        with patch.object(battery,'checkout',return_value={"commit":"b"*40}),patch.object(battery,'run_stage',side_effect=AssertionError('must not execute')):
            with self.assertRaises(ValueError):battery.run_battery(root,self.runs/'blocked',python=Path(sys.executable),experiment_contract=self.path)
        self.assertFalse((self.runs/'blocked').exists())
