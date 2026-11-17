"""E11.9 fail-closed owner-supplied text checks (no network or science votes)."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from klone.limbo_council_workbench import _fingerprint
from klone.limbo_fulltext_review import _read_source, review_fulltexts, main


def _fixture():
    first = "Alpha has 13.7% measured change."
    second = "Beta differs by 31 percentage points."
    cards = [
        {
            "candidate_id": "c1", "source": "A", "source_event_id": 26,
            "arxiv_id": "2611.13801v1",
            "original_publication_url": "https://arxiv.org/abs/2611.13801v1",
            "local_summary_quote": first,
            "local_quote_sha256": sha256(first.encode()).hexdigest(),
            "priority": 1,
            "measured_quantities_in_local_quote": [
                {"number": "13.7", "unit": "percent"}
            ],
        },
        {
            "candidate_id": "c2", "source": "B", "source_event_id": 24,
            "arxiv_id": "2611.15598v1",
            "original_publication_url": "https://arxiv.org/abs/2611.15598v1",
            "local_summary_quote": second,
            "local_quote_sha256": sha256(second.encode()).hexdigest(),
            "priority": 2,
            "measured_quantities_in_local_quote": [
                {"number": "31", "unit": "percentage_point"}
            ],
        },
    ]
    report = {
        "kind": "klone-e11-8-source-verification-cards",
        "source_event_ids": [26, 24],
        "source_snapshot_sha256": "e" * 64,
        "card_count": 2,
        "cards": cards,
    }
    report["report_sha256"] = _fingerprint(report)
    a = ("The original methods used measurements.  "
         "Alpha has 13.7% measured change.  " + "Study context. " * 15).encode()
    b = ("The original methods discussed an entirely separate outcome.  "
         "The manuscript also gives 31% as a share.  " + "Study context. " * 15).encode()
    return report, {"A": a, "B": b}


class E119Tests(unittest.TestCase):
    def setUp(self):
        self.cards, self.sources = _fixture()
        self.ids = {"A": "2611.13801v1", "B": "2611.15598v1"}
        self.notes = {"A": "Public source text supplied by owner",
                      "B": "Public source text supplied by owner"}

    def review(self, cards=None, sources=None, ids=None, notes=None, attest=True):
        expected = self.cards
        with patch("klone.limbo_fulltext_review.build_cards", return_value=expected):
            return review_fulltexts(
                Path("not-accessed.sqlite"), *([{}] * 8),
                cards if cards is not None else expected,
                sources if sources is not None else self.sources,
                declared_ids=ids if ids is not None else self.ids,
                rights_notes=notes if notes is not None else self.notes,
                owner_attests=attest,
            )

    def test_deterministic_and_explicitly_unverified(self):
        one = self.review()
        self.assertEqual(one, self.review())
        self.assertEqual(one["card_count"], 2)
        self.assertTrue(one["local_full_text_scanned"])
        self.assertFalse(one["original_arxiv_full_text_authenticated"])
        self.assertEqual(one["scientifically_verified_claims"], 0)
        self.assertEqual(one["council_reviews_performed"], 0)
        self.assertEqual(one["new_network_requests"], 0)
        self.assertFalse(one["memory_write"])
        self.assertFalse(any(one["authority"].values()))
        self.assertEqual(one["cards"][0]["full_text_lexical_class"],
                         "lexical_quote_found_unverified")
        self.assertEqual(len(one["cards"][0]["lexical_match_spans"]), 1)
        self.assertTrue(one["cards"][0]["unit_aware_numeric_mentions"][0][
            "mentioned_with_same_unit"])
        self.assertEqual(one["cards"][1]["full_text_lexical_class"],
                         "not_located_in_supplied_full_text_not_disproved")
        self.assertFalse(one["cards"][1]["unit_aware_numeric_mentions"][0][
            "mentioned_with_same_unit"])
        self.assertEqual(one["report_sha256"], _fingerprint({
            k: v for k, v in one.items() if k != "report_sha256"
        }))

    def test_partial_numeric_match_not_semantic_proof(self):
        alt = dict(self.sources)
        alt["B"] = (b"An unrelated table reports 31 percentage points. " +
                    b"Repetition of unrelated context. " * 13)
        report = self.review(sources=alt)
        row = report["cards"][1]
        self.assertEqual(row["full_text_lexical_class"],
                         "unit_aware_numbers_only_unverified")
        self.assertTrue(row["unit_aware_numeric_mentions"][0]["mentioned_with_same_unit"])
        self.assertFalse(row["scientific_claim_verified"])

    def test_whitespace_case_normalization_not_scientific_proof(self):
        alt = dict(self.sources)
        alt["A"] = (b"ALPHA HAS 13.7%\nMEASURED CHANGE. " +
                    b"Additional unrelated methods text. " * 13)
        report = self.review(sources=alt)
        self.assertEqual(report["cards"][0]["full_text_lexical_class"],
                         "lexical_quote_found_unverified")

    def test_attestation_rights_and_publication_version_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "owner confirmation"):
            self.review(attest=False)
        with self.assertRaisesRegex(ValueError, "usage-rights"):
            self.review(notes={"A": "x", "B": self.notes["B"]})
        with self.assertRaisesRegex(ValueError, "arXiv IDs"):
            self.review(ids={"A": "2611.13801", "B": self.ids["B"]})
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.review(ids={"A": self.ids["B"], "B": self.ids["A"]})
        with self.assertRaisesRegex(ValueError, "distinct"):
            self.review(ids={"A": self.ids["A"], "B": self.ids["A"]})

    def test_tampered_and_reordered_e118_fail_closed(self):
        changed = deepcopy(self.cards)
        changed["cards"][0]["priority"] = 4
        with self.assertRaisesRegex(ValueError, "stale, tampered"):
            self.review(cards=changed)
        changed = deepcopy(self.cards)
        changed["source_event_ids"] = [24, 26]
        with self.assertRaisesRegex(ValueError, "stale, tampered"):
            self.review(cards=changed)
        changed = deepcopy(self.cards)
        changed["report_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "stale, tampered"):
            self.review(cards=changed)

    def test_publisher_text_format_and_binary_limits(self):
        for content in (b"", b"%PDF-1.7 " + b"x" * 230,
                        b"<html>" + b"x" * 230,
                        b"\x00" + b"x" * 230, b"\xff" * 400,
                        b"x" * (2 * 1024 * 1024 + 1)):
            with self.subTest(prefix=content[:12]):
                with self.assertRaises(ValueError):
                    _read_source(content, "A")
        same = dict(self.sources)
        same["B"] = self.sources["A"]
        with self.assertRaisesRegex(ValueError, "identical"):
            self.review(sources=same)

    def test_reject_duplicate_or_wrong_source_cards(self):
        with patch("klone.limbo_fulltext_review.build_cards") as replay:
            bad = deepcopy(self.cards)
            bad["cards"][1]["candidate_id"] = bad["cards"][0]["candidate_id"]
            bad["cards"][1]["source"] = "A"
            bad["cards"][1]["source_event_id"] = 26
            bad["cards"][1]["arxiv_id"] = self.ids["A"]
            bad["cards"][1]["original_publication_url"] = (
                "https://arxiv.org/abs/" + self.ids["A"]
            )
            replay.return_value = bad
            with self.assertRaisesRegex(ValueError, "duplicate"):
                review_fulltexts(
                    Path("unused"), *([{}] * 8), bad, self.sources,
                    declared_ids=self.ids, rights_notes=self.notes,
                    owner_attests=True,
                )

    def test_cli_new_output_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            keys = ("original", "proposals", "selected", "ledger", "quality",
                    "queue", "receipt", "comparison", "cards")
            args = ["--klone-db", str(root / "no-database-read.sqlite")]
            for key in keys:
                filename = root / (key + ".json")
                filename.write_text(json.dumps(self.cards if key == "cards" else {}))
                args += ["--" + key, str(filename)]
            for role in ("a", "b"):
                source = root / (role + ".txt")
                source.write_bytes(self.sources[role.upper()])
                args += ["--source-" + role + "-file", str(source),
                         "--source-" + role + "-id", self.ids[role.upper()],
                         "--rights-note-" + role, self.notes[role.upper()]]
            result = root / "result.json"
            args += ["--owner-confirms-local-text", "--output", str(result)]
            with patch("klone.limbo_fulltext_review.build_cards",
                       return_value=self.cards):
                self.assertEqual(main(args), 0)
                first = result.read_bytes()
                with self.assertRaises(SystemExit):
                    main(args)
            self.assertEqual(first, result.read_bytes())
            self.assertFalse((root / "no-database-read.sqlite").exists())


if __name__ == "__main__":
    unittest.main()
