"""KLONE E11.11 tests: source identity, abstract/PDF disagreements, no promotions."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from klone.limbo_council_workbench import _fingerprint
from klone.limbo_abstract_pdf_diagnostics import diagnose_abstract_pdf, main


def fixture(root):
    a_id, b_id = "2611.13801v1", "2611.15598v1"
    a_abs = ("Alpha result appears on page one. " +
             "These are merely unverified reported outcomes. " * 4)
    b_abs = ("Abstract claim unique to Atom B. " +
             "This sentence has not been verified against the source PDF. " * 3)
    texts = {
        "A": "Alpha result appears on page one. Only in PDF for alpha. " +
             "Many other words are written in this manuscript. " * 4,
        "B": "This PDF page gives 31 percentage points. " +
             "Many additional unrelated observations are described. " * 5,
    }
    papers = {
        "A": root / (a_id + ".pdf"),
        "B": root / (b_id + ".pdf"),
    }
    for role, path in papers.items():
        path.write_bytes(("%PDF-1.7\n" + role + "\n%%EOF").encode())
    digests = {role: sha256(papers[role].read_bytes()).hexdigest()
               for role in ("A", "B")}
    meta = {
        "A": {"arxiv_id": a_id, "source_event_id": 26,
              "usage_rights_note": "Owner-supplied manuscript text"},
        "B": {"arxiv_id": b_id, "source_event_id": 24,
              "usage_rights_note": "Owner-supplied manuscript text"},
    }
    e119 = {"sources": meta, "schema_version": 1}
    receipt = {
        "report_sha256": "e" * 64,
        "documents": [
            {"arxiv_id": a_id, "memory_event_id": 26,
             "abstract_from_arxiv": a_abs,
             "abstract_sha256": sha256(a_abs.encode()).hexdigest()},
            {"arxiv_id": b_id, "memory_event_id": 24,
             "abstract_from_arxiv": b_abs,
             "abstract_sha256": sha256(b_abs.encode()).hexdigest()},
        ],
    }
    source_cards = [
        ("a1", "A", "Alpha result appears on page one."),
        ("b1", "B", "Abstract claim unique to Atom B."),
        ("a2", "A", "Only in PDF for alpha."),
        ("b2", "B", "The model shows 31 percentage points."),
        ("b3", "B", "Tekstinmuotoinen tuntematon väite."),
    ]
    e118 = {"cards": [{
        "candidate_id": key, "source": role,
        "source_content_origin": "owner_supplied_unverified",
        "local_summary_quote": quote,
        "local_quote_sha256": sha256(quote.encode()).hexdigest(),
    } for key, role, quote in source_cards]}
    rows = [
        ("a1", "A", "2611.13801v1", "literal_page_quote_unverified",
         [{"page": 1, "char_start": 0, "char_end": 33}], [], []),
        ("b1", "B", "2611.15598v1", "not_located_on_pdf_pages_not_disproved",
         [], [], []),
        ("a2", "A", "2611.13801v1", "literal_page_quote_unverified",
         [{"page": 1, "char_start": 35, "char_end": 58}], [], []),
        ("b2", "B", "2611.15598v1", "numbers_on_pages_only_unverified",
         [], [], [{"page": 1}]),
        ("b3", "B", "2611.15598v1", "not_located_on_pdf_pages_not_disproved",
         [], [], []),
    ]
    locator = {
        "kind": "klone-e11-10-local-pdf-page-locator",
        "e11_9_report_sha256": "9" * 64,
        "source_snapshot_sha256": "1" * 64,
        "pdf_sources": {
            role: {
                "arxiv_id": meta[role]["arxiv_id"],
                "pdf_sha256": digests[role],
                "page_count": 1,
            } for role in ("A", "B")
        },
        "cards": [
            {"candidate_id": key, "source": role,
             "arxiv_id": arxiv, "page_locator_status": status,
             "literal_page_spans": literal,
             "normalized_page_spans": normal,
             "numeric_page_mentions": numerical}
            for key, role, arxiv, status, literal, normal, numerical in rows
        ],
    }
    locator["report_sha256"] = _fingerprint(locator)
    return e118, e119, receipt, locator, papers, digests, texts


class E1111Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.cards, self.fulltext, self.receipt, self.locator,
         self.pdfs, self.digests, self.texts) = fixture(self.root)

    def review(self, *, locator=None, receipt=None, cards=None, attests=True):
        actual_locator = self.locator
        with patch("klone.limbo_abstract_pdf_diagnostics.inspect_pdfs",
                   return_value=actual_locator):
            with patch("klone.limbo_abstract_pdf_diagnostics._pages",
                       side_effect=lambda path: [self.texts["A" if
                        "13801" in str(path) else "B"]]):
                return diagnose_abstract_pdf(
                    Path("no-database-read"), *([{}] * 6),
                    receipt if receipt is not None else self.receipt,
                    {}, cards if cards is not None else self.cards,
                    self.fulltext,
                    locator if locator is not None else actual_locator,
                    {"A": b"A", "B": b"B"}, self.pdfs, self.digests,
                    owner_attests=attests,
                )

    def test_differentiates_four_surfaces_without_truth_promotion(self):
        r = self.review()
        self.assertEqual(r, self.review())
        self.assertEqual(r["card_count"], 5)
        states = {c["candidate_id"]: c["discrepancy_class"]
                  for c in r["cards"]}
        self.assertEqual(states["a1"], "atom_quote_and_pdf_page_match_unverified")
        self.assertEqual(states["b1"], "atom_verbatim_quote_missing_in_pdf_page_text")
        self.assertEqual(states["a2"], "pdf_page_quote_not_in_atom_abstract")
        self.assertEqual(states["b2"], "only_unit_aware_numbers_on_pdf_pages")
        self.assertEqual(states["b3"], "no_textual_correspondence_found_not_disproved")
        self.assertTrue(r["sources"]["A"][
            "entire_atom_abstract_on_single_pdf_page"] == [])
        self.assertEqual(r["scientifically_verified_claims"], 0)
        self.assertEqual(r["council_reviews_performed"], 0)
        self.assertEqual(r["new_network_requests"], 0)
        self.assertFalse(r["memory_write"])
        self.assertFalse(any(r["authority"].values()))
        self.assertEqual(r["report_sha256"], _fingerprint({
            k: v for k, v in r.items() if k != "report_sha256"}))

    def test_consent_and_tampered_e1110_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "owner approval"):
            self.review(attests=False)
        bad = deepcopy(self.locator)
        bad["cards"][0]["page_locator_status"] = "scientifically_verified"
        with self.assertRaisesRegex(ValueError, "stale, tampered"):
            self.review(locator=bad)

    def test_wrong_receipt_abstract_digest_rejected(self):
        bad = deepcopy(self.receipt)
        bad["documents"][1]["abstract_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "abstract text or SHA"):
            self.review(receipt=bad)

    def test_wrong_source_event_rejected(self):
        bad = deepcopy(self.receipt)
        bad["documents"][1]["memory_event_id"] = 26
        with self.assertRaisesRegex(ValueError, "event ID"):
            self.review(receipt=bad)

    def test_no_duplicate_source_cards(self):
        bad = deepcopy(self.cards)
        bad["cards"].append(deepcopy(bad["cards"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.review(cards=bad)

    def test_cli_writes_once_with_no_network_or_memory_access(self):
        args = ["--klone-db", str(self.root / "never-opened.sqlite")]
        for key in ("original", "proposals", "selected", "ledger", "quality",
                    "queue", "receipt", "comparison", "cards", "fulltext",
                    "pdf-report"):
            path = self.root / (key + ".json")
            value = (self.receipt if key == "receipt" else
                     self.cards if key == "cards" else
                     self.fulltext if key == "fulltext" else
                     self.locator if key == "pdf-report" else {})
            path.write_text(json.dumps(value))
            args += ["--" + key, str(path)]
        for role in ("a", "b"):
            upper = role.upper()
            path = self.root / (role + ".txt")
            path.write_bytes(self.texts[upper].encode())
            args += [
                "--pdf-" + role, str(self.pdfs[upper]),
                "--pdf-" + role + "-sha256", self.digests[upper],
                "--text-" + role, str(path),
            ]
        output = self.root / "e1111.json"
        args += ["--owner-approves-abstract-pdf", "--output", str(output)]
        with patch("klone.limbo_abstract_pdf_diagnostics.inspect_pdfs",
                   return_value=self.locator):
            with patch("klone.limbo_abstract_pdf_diagnostics._pages",
                       side_effect=lambda path: [self.texts["A" if
                        "13801" in str(path) else "B"]]):
                self.assertEqual(main(args), 0)
                saved = output.read_bytes()
                with self.assertRaises(SystemExit):
                    main(args)
        self.assertEqual(saved, output.read_bytes())
        self.assertFalse((self.root / "never-opened.sqlite").exists())


if __name__ == "__main__":
    unittest.main()
