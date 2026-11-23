"""Dependency audit: synthetic fixtures only, no network or GitHub writes."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools" / "klone_pr_train.py"
SPEC = importlib.util.spec_from_file_location("klone_pr_train", PATH)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def pr(number, head, base="main", draft=True, state="open"):
    return {"number": number, "head": {"ref": head}, "base": {"ref": base},
            "draft": draft, "state": state}


class TrainTests(unittest.TestCase):
    def test_stacked_chain_and_independent(self):
        data = [pr(183, "knowledge", "quality"), pr(182, "quality", "bridge"),
                pr(181, "bridge", "limbo"), pr(177, "limbo"), pr(184, "reality")]
        r = mod.audit(data)
        self.assertEqual(r["review_order_not_merge_permission"], [177, 184, 181, 182, 183])
        self.assertEqual(r["open_count"], 5)
        self.assertEqual(r["direct_main_count"], 2)
        self.assertEqual(r["pull_requests"][2]["depends_on"], [181])
        self.assertFalse(r["automatic_merge_authority"])
        self.assertFalse(r["android_verified"])

    def test_unresolved_base_cannot_be_called_safe(self):
        r = mod.audit([pr(18, "upper", "absent")])
        self.assertEqual(r["unresolved_base_prs"], [18])
        self.assertEqual(r["review_order_not_merge_permission"], [])
        self.assertEqual(r["pull_requests"][0]["status"], "unknown_base")

    def test_cycle_is_not_a_review_order(self):
        r = mod.audit([pr(1, "a", "b"), pr(2, "b", "a"), pr(3, "c", "a")])
        self.assertEqual(r["review_order_not_merge_permission"], [])
        self.assertEqual(r["cycle_or_blocked_prs"], [1, 2, 3])

    def test_invalid_records_fail_closed(self):
        cases = ["nonsense", {}, [pr(True, "branch")], [pr(1, "b"), pr(1, "c")],
                 [pr(1, "b"), pr(2, "b")], [pr(1, "../bad")],
                 [pr(1, "bad//branch")], [dict(pr(1, "a"), draft="false")],
                 [dict(pr(1, "a"), state="unknown")]]
        for case in cases:
            with self.subTest(case=str(case)[:40]):
                with self.assertRaises(ValueError):
                    mod.audit(case)

    def test_closed_pr_does_not_provide_open_dependency(self):
        r = mod.audit([pr(1, "base", state="closed", draft=False), pr(2, "new", "base")])
        self.assertEqual(r["unresolved_base_prs"], [2])

    def test_determinism(self):
        data = [pr(2, "b", "a"), pr(1, "a")]
        self.assertEqual(json.dumps(mod.audit(data), sort_keys=True), json.dumps(mod.audit(data), sort_keys=True))

    def test_cli_offline_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "snapshot.json"
            source.write_text(json.dumps([pr(7, "z")]), encoding="utf-8")
            cp = subprocess.run([sys.executable, str(PATH), str(source)], capture_output=True, text=True)
            self.assertEqual(cp.returncode, 0, cp.stderr)
            self.assertEqual(json.loads(cp.stdout)["review_order_not_merge_permission"], [7])
            link = root / "link.json"
            try:
                link.symlink_to(source)
            except OSError:
                self.skipTest("symlink unavailable")
            blocked = subprocess.run([sys.executable, str(PATH), str(link)], capture_output=True, text=True)
            self.assertEqual(blocked.returncode, 2)
            self.assertEqual(len(list(root.iterdir())), 2)


if __name__ == "__main__":
    unittest.main()
