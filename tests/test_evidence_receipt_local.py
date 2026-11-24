"""Optional integration with actual E11 reports on the user's Termux device."""
import json
import secrets
import unittest
from pathlib import Path
from klone.evidence_receipt import EvidenceError, make_subject, sign, verify

ROOT = Path.home() / "klone-var/e11"
DEBATE = ROOT / "council72-quality-debate-live-20261119-121640-21516.json"
DOSSIER = ROOT / "e11-11-abstrakti-pdf-erot-20261117-151610.json"


@unittest.skipUnless(DEBATE.is_file() and DOSSIER.is_file(), "local E11 reports not present")
class LocalE11Tests(unittest.TestCase):
    def test_real_argument_source_binding(self):
        def load(path):
            if path.is_symlink() or path.stat().st_size > 3_000_000:
                raise EvidenceError("invalid_lab_path")
            return json.loads(path.read_text(encoding="utf-8"))
        debate, dossier = load(DEBATE), load(DOSSIER)
        arguments = [a for t in debate["debate_turns"]
                     if t["stage"] in ("cross_examination", "defense")
                     for a in t["answer"]["arguments"]]
        self.assertEqual(len(arguments), 6)
        key = secrets.token_bytes(32)
        for i, arg in enumerate(arguments):
            with self.subTest(argument=i):
                subject = make_subject(proposal_id=f"test-{i}", target_version="lab-v1",
                                       draft_text="Test-only, unverified research draft",
                                       ids=arg["source_card_ids"], debate=debate, dossier=dossier)
                self.assertEqual(subject["distinct_arxiv_works"], 2)
                self.assertTrue(verify(sign(subject, secret=key, issued_at=1000),
                                       subject, secret=key, now=1001))
