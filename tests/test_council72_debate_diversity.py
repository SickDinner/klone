"""No-network, no-write regression checks for Council72 debate diversity."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "src/klone/council72_debate_diversity.py"
spec = importlib.util.spec_from_file_location("council72_diversity", PATH)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def report():
    def arg(text, card):
        return {"claim": "Kysymys liittyy alkuperäiseen tutkimukseen.",
                "challenge_or_defense": "Tekstistä ei voi päätellä tieteellistä totuutta.",
                "falsification_test": text,
                "source_card_ids": [card]}
    r = {
        "kind": "klone-council72-adversarial-debate-v1", "schema_version": 1,
        "mode": "three_turn_debate_completed",
        "owner_review_required": True, "scientific_truth_verified": False, "memory_write": False,
        "model_api_requests_performed": 0, "model_api_responses_reused": 3,
        "debate_turns": [
            {"stage": "cross_examination", "answer": {"stance": "cross_examination",
             "role_focus_ids": [31, 50, 66], "arguments": [arg(
              "Tarkista alkuperäinen Atom-tiivistelmä ja PDF-sivu.", "card1")]}},
            {"stage": "defense", "answer": {"stance": "defense",
             "role_focus_ids": [31, 50, 66], "arguments": [arg(
              "Tarkista alkuperäinen Atom-tiivistelmä ja PDF-sivu.", "card1")]}},
            {"stage": "arbiter", "answer": {"decision": "owner_review_required",
             "falsifiable_next_tests": ["Tarkista alkuperäinen Atom-tiivistelmä ja PDF-sivu."]}}
        ],
    }
    r["report_sha256"] = audit._fingerprint(r)
    return r


def fixhash(r):
    r.pop("report_sha256", None)
    r["report_sha256"] = audit._fingerprint(r)
    return r


class DebateDiversityAuditTests(unittest.TestCase):
    def test_realistic_same_five_roles_flagged(self):
        r = report()
        r["debate_turns"][0]["answer"]["role_focus_ids"] = [31, 50, 66, 55, 40]
        r["debate_turns"][1]["answer"]["role_focus_ids"] = [31, 50, 66, 55, 40]
        result = audit.analyze(fixhash(r))
        self.assertEqual(result["shared_role_ids"], [31, 40, 50, 55, 66])
        self.assertEqual(result["role_overlap_jaccard"], 1.0)
        self.assertIn("same_focal_role_set", result["screening_flags"])
        self.assertIn("similar_falsification_tests_candidate", result["screening_flags"])
        self.assertFalse(result["independent_models_verified"])

    def test_disjoint_roles_and_sources(self):
        r = report()
        r["debate_turns"][1]["answer"]["role_focus_ids"] = [1, 2, 3]
        r["debate_turns"][1]["answer"]["arguments"][0]["source_card_ids"] = ["card2"]
        result = audit.analyze(fixhash(r))
        self.assertEqual(result["role_overlap_jaccard"], 0.0)
        self.assertEqual(result["source_card_overlap_jaccard"], 0.0)
        self.assertNotIn("same_focal_role_set", result["screening_flags"])

    def test_tampered_payload_rejected(self):
        r = report()
        r["debate_turns"][1]["answer"]["role_focus_ids"] = [20]
        with self.assertRaisesRegex(ValueError, "hash"):
            audit.analyze(r)

    def test_bad_role_and_bad_stance(self):
        r = report()
        r["debate_turns"][1]["answer"]["role_focus_ids"] = [True]
        with self.assertRaisesRegex(ValueError, "role"):
            audit.analyze(fixhash(r))
        r = report()
        r["debate_turns"][0]["answer"]["stance"] = "defense"
        with self.assertRaisesRegex(ValueError, "stance"):
            audit.analyze(fixhash(r))

    def test_unsafe_counter_and_authority(self):
        r = report()
        r["model_api_requests_performed"] = 2
        with self.assertRaisesRegex(ValueError, "counter"):
            audit.analyze(fixhash(r))
        r = report()
        r["scientific_truth_verified"] = True
        with self.assertRaisesRegex(ValueError, "completed debate"):
            audit.analyze(fixhash(r))

    def test_duplicate_cards_and_malformed_arguments(self):
        r = report()
        r["debate_turns"][0]["answer"]["arguments"][0]["source_card_ids"] = ["card1", "card1"]
        with self.assertRaisesRegex(ValueError, "card"):
            audit.analyze(fixhash(r))
        r = report()
        r["debate_turns"][0]["answer"]["arguments"] = []
        with self.assertRaisesRegex(ValueError, "argument"):
            audit.analyze(fixhash(r))

    def test_same_research_issues_with_different_wording(self):
        r = report()
        r["debate_turns"][0]["answer"]["arguments"][0]["falsification_test"] = (
            "Varmista PDF-tekstikerroksesta sama arXiv-versio ja sanatarkka osuma."
        )
        r["debate_turns"][1]["answer"]["arguments"][0]["falsification_test"] = (
            "Tutki sivukuvista versiovastaavuus ja katkelman täsmällinen vastine."
        )
        result = audit.analyze(fixhash(r))
        self.assertEqual(result["issue_axis_overlap_jaccard"], 1.0)
        self.assertEqual(len(result["shared_issue_axes"]), 3)
        self.assertIn("shared_issue_axes_candidate", result["screening_flags"])
        self.assertLess(result["falsification_test_similarity_max_per_cross_argument"][0], 0.6)

    def test_different_research_issue_axes(self):
        r = report()
        r["debate_turns"][0]["answer"]["arguments"][0]["falsification_test"] = (
            "Varmista sama julkaisuversio ennen jatkotarkistusta."
        )
        r["debate_turns"][1]["answer"]["arguments"][0]["falsification_test"] = (
            "Arvioi RMSE-mittari ja tutkimusmenetelmän laskennan oikeellisuus."
        )
        result = audit.analyze(fixhash(r))
        self.assertEqual(result["issue_axis_overlap_jaccard"], 0.0)
        self.assertIn("numeric_context", result["unmatched_defender_issue_axes"])
        self.assertNotIn("shared_issue_axes_candidate", result["screening_flags"])

    def test_no_known_issue_cues_is_unknown_not_diverse(self):
        result = audit.analyze(report())
        self.assertEqual(result["cross_examiner_issue_axes"], [])
        self.assertEqual(result["defender_issue_axes"], [])
        self.assertEqual(result["issue_axis_overlap_jaccard"], 0.0)
        self.assertNotIn("shared_issue_axes_candidate", result["screening_flags"])
        self.assertFalse(result["independent_models_verified"])

    def test_determinism(self):
        r = report()
        self.assertEqual(audit.analyze(r), audit.analyze(deepcopy(r)))

    def test_cli_offline_symlink_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "report.json"
            p.write_text(json.dumps(report(), ensure_ascii=False), encoding="utf-8")
            result = subprocess.run([sys.executable, str(PATH), str(p), "--text"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Jaccard", result.stdout)
            link = Path(tmp) / "link.json"
            try:
                link.symlink_to(p)
            except OSError:
                self.skipTest("symlink not supported")
            denied = subprocess.run([sys.executable, str(PATH), str(link)],
                                    capture_output=True, text=True)
            self.assertEqual(denied.returncode, 2)


if __name__ == "__main__":
    unittest.main()
