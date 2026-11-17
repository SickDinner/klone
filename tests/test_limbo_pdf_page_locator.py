"""E11.10 research PDF page locator: bounded, source-bound and read-only."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from klone.limbo_council_workbench import _fingerprint
from klone.limbo_pdf_page_locator import (
    _normalize, _pages, _read_input, inspect_pdfs, main,
)


def fixture(root: Path):
    quote_a = "Alpha has 13.7% measured change."
    quote_b = "The Beta model shows 31 percentage points improvement."
    page_a = (quote_a + " The outcome is disputed. " + "other information " * 16)
    page_b = ("The Be-\nta model shows 31 percentage points improvement. " +
              "More information " * 18)
    text_a = page_a + "\f"
    text_b = page_b + "\f"
    raw_a, raw_b = text_a.encode(), text_b.encode()
    pdfs = {}
    expected = {}
    for role in ("A", "B"):
        path = root / (role + ".pdf")
        path.write_bytes(("%PDF-1.7\n" + role + "\n%%EOF\n").encode())
        pdfs[role] = path
        expected[role] = sha256(path.read_bytes()).hexdigest()

    report = {
        "kind": "klone-e11-9-owner-fulltext-lexical-review",
        "schema_version": 1,
        "source_snapshot_sha256": "a" * 64,
        "e11_8_report_sha256": "b" * 64,
        "source_event_ids": [26, 24],
        "sources": {
            role: {
                "arxiv_id": ("2611.13801v1" if role == "A" else "2611.15598v1"),
                "source_event_id": (26 if role == "A" else 24),
                "usage_rights_note": "local authorized research reading",
                "text_sha256": sha256(raw_a if role == "A" else raw_b).hexdigest(),
            }
            for role in ("A", "B")
        },
        "card_count": 2,
        "cards": [
            {
                "candidate_id": "c1", "source": "A",
                "arxiv_id": "2611.13801v1",
                "unit_aware_numeric_mentions": [{
                    "number": "13.7", "unit": "percent",
                    "mentioned_with_same_unit": True
                }],
                "full_text_lexical_class": "lexical_quote_found_unverified",
            },
            {
                "candidate_id": "c2", "source": "B",
                "arxiv_id": "2611.15598v1",
                "unit_aware_numeric_mentions": [{
                    "number": "31", "unit": "percentage_point",
                    "mentioned_with_same_unit": True
                }],
                "full_text_lexical_class": "unit_aware_numbers_only_unverified",
            },
        ],
    }
    report["report_sha256"] = _fingerprint(report)
    cards = {"cards": [
        {"candidate_id": "c1", "source": "A",
         "local_summary_quote": quote_a},
        {"candidate_id": "c2", "source": "B",
         "local_summary_quote": quote_b},
    ]}
    return report, cards, {"A": raw_a, "B": raw_b}, pdfs, expected, {
        "A": [page_a, "Completely different second page."],
        "B": [page_b, "Completely different second page."],
    }


class PDFPageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.report, self.cards, self.texts, self.pdfs, self.expected,
         self.pages) = fixture(self.root)

    def execute(self, command, *, limit):
        role = Path(command[-2] if command[0] == "pdftotext"
                    else command[-1]).stem
        if command[0] == "pdfinfo":
            return b"Pages: 2\n"
        if "-f" in command:
            num = int(command[command.index("-f") + 1])
            return (self.pages[role][num - 1] + "\f").encode()
        return self.texts[role]

    def inspect(self, *, report=None, cards=None, texts=None,
                expected=None, attest=True):
        with patch("klone.limbo_pdf_page_locator.review_fulltexts",
                   return_value=self.report):
            with patch("klone.limbo_pdf_page_locator._execute",
                       side_effect=self.execute):
                return inspect_pdfs(
                    Path("not-accessed.db"), *([{}] * 8),
                    cards if cards is not None else self.cards,
                    report if report is not None else self.report,
                    texts if texts is not None else self.texts,
                    self.pdfs,
                    expected if expected is not None else self.expected,
                    owner_attests=attest,
                )

    def test_page_numbers_and_typography_recovery_are_not_scientific_proof(self):
        result = self.inspect()
        self.assertEqual(result, self.inspect())
        self.assertEqual(result["card_count"], 2)
        self.assertEqual(result["cards"][0]["page_locator_status"],
                         "literal_page_quote_unverified")
        self.assertEqual(result["cards"][0]["literal_page_spans"][0]["page"], 1)
        self.assertEqual(result["cards"][1]["page_locator_status"],
                         "typography_normalized_page_quote_unverified")
        self.assertEqual(result["cards"][1]["normalized_page_spans"][0]["page"], 1)
        self.assertTrue(result["pdf_sources"]["B"]["text_identical_to_e11_9"])
        self.assertFalse(result["arxiv_publisher_pdf_authenticated"])
        self.assertEqual(result["scientifically_verified_claims"], 0)
        self.assertEqual(result["new_network_requests"], 0)
        self.assertFalse(result["memory_write"])
        self.assertFalse(any(result["authority"].values()))

    def test_reflow_does_not_equate_distinct_measurements(self):
        self.assertEqual(_normalize("The Be-\nta is 31 percentage points."),
                         "the beta is 31 percentage points.")
        self.assertNotEqual(_normalize("31%"), _normalize("31 percentage points"))
        self.assertNotEqual(_normalize("0.997 K"), _normalize("0.997%"))

    def test_explicit_owner_authorization_required(self):
        with self.assertRaisesRegex(ValueError, "explicit owner"):
            self.inspect(attest=False)

    def test_tampered_e119_detected_before_pdf_parsing(self):
        r = deepcopy(self.report)
        r["sources"]["A"]["text_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "E11.9 source report stale"):
            self.inspect(report=r)

    def test_wrong_pdf_hash_fails_closed(self):
        wrong = dict(self.expected)
        wrong["B"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "PDF SHA-256"):
            self.inspect(expected=wrong)

    def test_pdf_extract_drift_detected(self):
        with patch("klone.limbo_pdf_page_locator.review_fulltexts",
                   return_value=self.report):
            def changed(cmd, *, limit):
                if cmd[0] == "pdftotext" and "-f" not in cmd:
                    return b"Unrelated full extracted content " * 10
                return self.execute(cmd, limit=limit)
            with patch("klone.limbo_pdf_page_locator._execute",
                       side_effect=changed):
                with self.assertRaisesRegex(ValueError, "PDF extraction not identical"):
                    inspect_pdfs(Path("unused"), *([{}] * 8),
                                 self.cards, self.report, self.texts,
                                 self.pdfs, self.expected, owner_attests=True)

    def test_unsafe_or_missing_pdf_is_rejected(self):
        bad = self.pdfs["A"]
        bad.write_bytes(b"<html>" + b"x" * 300 + b"%%EOF\n")
        with self.assertRaisesRegex(ValueError, "complete PDF"):
            self.inspect()

    def test_limit_on_pdf_pages(self):
        with patch("klone.limbo_pdf_page_locator._execute",
                   return_value=b"Pages: 1000\n"):
            with self.assertRaisesRegex(ValueError, "page count"):
                _pages(self.pdfs["A"])

    def test_cli_creates_only_new_report(self):
        for role in ("A", "B"):
            (self.root / (role + ".txt")).write_bytes(self.texts[role])
        args = ["--klone-db", str(self.root / "unused-db")]
        for key in ("original", "proposals", "selected", "ledger", "quality",
                    "queue", "receipt", "comparison", "cards", "fulltext"):
            path = self.root / (key + ".json")
            path.write_text(json.dumps(
                self.report if key == "fulltext" else
                self.cards if key == "cards" else {}
            ))
            args += ["--" + key, str(path)]
        for role in ("a", "b"):
            upper = role.upper()
            args += [
                "--pdf-" + role, str(self.pdfs[upper]),
                "--text-" + role, str(self.root / (upper + ".txt")),
                "--pdf-" + role + "-sha256", self.expected[upper],
            ]
        target = self.root / "pdf-output.json"
        args += ["--owner-approves-local-pdf", "--output", str(target)]
        with patch("klone.limbo_pdf_page_locator.review_fulltexts",
                   return_value=self.report):
            with patch("klone.limbo_pdf_page_locator._execute",
                       side_effect=self.execute):
                self.assertEqual(main(args), 0)
                old = target.read_bytes()
                with self.assertRaises(SystemExit):
                    main(args)
        self.assertEqual(old, target.read_bytes())
        self.assertFalse((self.root / "unused-db").exists())


if __name__ == "__main__":
    unittest.main()
