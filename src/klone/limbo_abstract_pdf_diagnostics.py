"""KLONE E11.11: offline arXiv Atom abstract vs local PDF discrepancy triage.

Replays all previous E11 evidence before comparing two distinct text surfaces.
No network, semantic translations, research approvals, agents, or memory writes.
The Atom abstract is from a previously owner-approved metadata receipt;
the PDF is a local owner-supplied copy, not publisher-authenticated.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from .evidence_io import json_object, write_new_report
from .limbo_council_workbench import _fingerprint
from .limbo_evidence_review import MAX_MANIFEST_BYTES, _read_input
from .limbo_fulltext_review import MAX_SOURCE_BYTES
from .limbo_pdf_page_locator import (
    HEX_SHA256, _normalize, _pages, _candidate_pages, inspect_pdfs,
)

MAX_ABSTRACT_CHARS = 12000


def _source_documents(receipt, source_data):
    if type(receipt) is not dict or type(receipt.get("documents")) is not list:
        raise ValueError("verified E11.6 Atom receipt required")
    if len(receipt["documents"]) != 2:
        raise ValueError("exactly two arXiv Atom sources required")
    by_role = {}
    for role in ("A", "B"):
        expected = source_data[role]
        matching = [
            doc for doc in receipt["documents"]
            if type(doc) is dict and
            doc.get("arxiv_id") == expected["arxiv_id"] and
            doc.get("memory_event_id") == expected["source_event_id"]
        ]
        if len(matching) != 1:
            raise ValueError("E11.6 publication version or event ID mismatch")
        doc = matching[0]
        abstract = doc.get("abstract_from_arxiv")
        if (type(abstract) is not str or
            not 30 <= len(abstract) <= MAX_ABSTRACT_CHARS or
            doc.get("abstract_sha256") != sha256(
                abstract.encode("utf-8")).hexdigest()):
            raise ValueError("E11.6 abstract text or SHA differs")
        by_role[role] = doc
    if by_role["A"] is by_role["B"]:
        raise ValueError("duplicate E11.6 source")
    return by_role


def diagnose_abstract_pdf(
    core_db, original, proposals, selected, ledger, quality, queue,
    receipt, comparison, cards, fulltext, pdf_report,
    text_inputs, pdf_paths, expected_pdf_sha256, *, owner_attests=False,
):
    """Re-run E11.10 before interpreting any discrepancies. No promotions."""
    if owner_attests is not True:
        raise ValueError("explicit separate owner approval required")
    if type(pdf_report) is not dict:
        raise ValueError("E11.10 report required")
    rebuilt = inspect_pdfs(
        core_db, original, proposals, selected, ledger, quality,
        queue, receipt, comparison, cards, fulltext, text_inputs,
        pdf_paths, expected_pdf_sha256, owner_attests=True,
    )
    if (rebuilt != pdf_report or
        pdf_report.get("report_sha256") != _fingerprint({
            k: v for k, v in pdf_report.items() if k != "report_sha256"
        })):
        raise ValueError("E11.10 PDF report stale, tampered or source mismatch")
    if (type(cards) is not dict or type(cards.get("cards")) is not list or
        type(fulltext) is not dict or type(fulltext.get("sources")) is not dict):
        raise ValueError("E11.8/E11.9 reports required")

    docs = _source_documents(receipt, fulltext["sources"])
    page_text = {r: _pages(Path(pdf_paths[r]).expanduser())
                 for r in ("A", "B")}
    source_summaries = {}
    for role in ("A", "B"):
        metadata = rebuilt["pdf_sources"][role]
        if (len(page_text[role]) != metadata["page_count"] or
            metadata["pdf_sha256"] != expected_pdf_sha256[role] or
            metadata["arxiv_id"] != docs[role]["arxiv_id"]):
            raise ValueError("local PDF metadata differs from verified E11.10")
        abstract = docs[role]["abstract_from_arxiv"]
        normalized = _normalize(abstract)
        complete_matches = [
            i for i, text in enumerate(page_text[role], 1)
            if normalized and normalized in _normalize(text)
        ]
        source_summaries[role] = {
            "arxiv_id": docs[role]["arxiv_id"],
            "source_event_id": docs[role]["memory_event_id"],
            "arxiv_atom_abstract_sha256": docs[role]["abstract_sha256"],
            "local_pdf_sha256": metadata["pdf_sha256"],
            "pdf_page_count": metadata["page_count"],
            "entire_atom_abstract_on_single_pdf_page": complete_matches,
            "possible_abstract_pages_token_overlap_not_evidence":
                _candidate_pages(page_text[role], abstract),
            "full_abstract_missing_as_contiguous_text_is_not_disproof": True,
            "publisher_pdf_authenticated": False,
        }

    e118 = {(c["candidate_id"], c["source"]): c for c in cards["cards"]}
    if len(e118) != len(cards["cards"]):
        raise ValueError("duplicate E11.8 source cards")
    detailed = []
    for prior in rebuilt["cards"]:
        key = (prior["candidate_id"], prior["source"])
        if key not in e118:
            raise ValueError("E11.10 card absent from E11.8")
        old = e118[key]
        role = prior["source"]
        quote = old["local_summary_quote"]
        abstract = docs[role]["abstract_from_arxiv"]
        in_atom = quote.casefold().strip() in abstract.casefold()
        on_page = bool(prior["literal_page_spans"] or
                       prior["normalized_page_spans"])
        if in_atom and on_page:
            state = "atom_quote_and_pdf_page_match_unverified"
        elif in_atom:
            state = "atom_verbatim_quote_missing_in_pdf_page_text"
        elif on_page:
            state = "pdf_page_quote_not_in_atom_abstract"
        elif prior["numeric_page_mentions"]:
            state = "only_unit_aware_numbers_on_pdf_pages"
        else:
            state = "no_textual_correspondence_found_not_disproved"
        detailed.append({
            "candidate_id": key[0],
            "source": role,
            "arxiv_id": prior["arxiv_id"],
            "source_content_origin": old["source_content_origin"],
            "quote_sha256": old["local_quote_sha256"],
            "quote_sample_for_owner_review": quote[:240],
            "atom_abstract_sha256": docs[role]["abstract_sha256"],
            "pdf_sha256": rebuilt["pdf_sources"][role]["pdf_sha256"],
            "verbatim_in_atom_abstract": in_atom,
            "literal_pdf_pages": [m["page"] for m in
                                  prior["literal_page_spans"]],
            "typography_normalized_pdf_pages": [m["page"] for m in
                                                  prior["normalized_page_spans"]],
            "numeric_pdf_pages": [m["page"] for m in
                                  prior["numeric_page_mentions"]],
            "pdf_page_locator_class": prior["page_locator_status"],
            "discrepancy_class": state,
            "owner_review_questions": [
                "Is this local statement a translation/paraphrase rather than a quote?",
                "Does the PDF abstract differ in wording from the arXiv Atom abstract?",
                "Is a table, formula, page break or PDF extraction artifact involved?",
                "Do the same numbers refer to the same metric, baseline and cohort?",
                "Are PDF source version and document authenticity independently established?",
            ],
            "scientific_claim_verified": False,
            "council_review_completed": False,
        })
    result = {
        "kind": "klone-e11-11-arxiv-abstract-pdf-discrepancy-audit",
        "schema_version": 1,
        "e11_10_report_sha256": rebuilt["report_sha256"],
        "e11_9_report_sha256": rebuilt["e11_9_report_sha256"],
        "e11_6_atom_receipt_sha256": receipt["report_sha256"],
        "source_snapshot_sha256": rebuilt["source_snapshot_sha256"],
        "sources": source_summaries,
        "card_count": len(detailed),
        "cards": detailed,
        "diagnostic_scope": "lexical_surfaces_only_not_scientific_claim_review",
        "original_pdf_publisher_authenticated": False,
        "scientifically_verified_claims": 0,
        "council_reviews_performed": 0,
        "new_network_requests": 0,
        "memory_write": False,
        "authority": {
            "publisher_authentication": False,
            "scientific_truth": False,
            "independent_replication": False,
            "autonomous_council_review": False,
            "memory_write": False,
            "network_actions": False,
        },
    }
    result["report_sha256"] = _fingerprint(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="KLONE E11.11 offline arXiv Atom/PDF surface discrepancy audit"
    )
    parser.add_argument("--klone-db", type=Path, required=True)
    for key in ("original", "proposals", "selected", "ledger", "quality",
                "queue", "receipt", "comparison", "cards", "fulltext",
                "pdf-report"):
        parser.add_argument("--" + key, type=Path, required=True)
    for role in ("a", "b"):
        parser.add_argument("--pdf-" + role, type=Path, required=True)
        parser.add_argument("--pdf-" + role + "-sha256", required=True)
        parser.add_argument("--text-" + role, type=Path, required=True)
    parser.add_argument("--owner-approves-abstract-pdf", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    keys = ("original", "proposals", "selected", "ledger", "quality",
            "queue", "receipt", "comparison", "cards", "fulltext", "pdf_report")
    try:
        docs = [
            json_object(_read_input(getattr(args, key),
                                    MAX_MANIFEST_BYTES, "E11.11-" + key))
            for key in keys
        ]
        texts = {
            role: _read_input(getattr(args, "text_" + role.lower()),
                              MAX_SOURCE_BYTES, "E11.11-text-" + role)
            for role in ("A", "B")
        }
        report = diagnose_abstract_pdf(
            args.klone_db, *docs, texts,
            {"A": args.pdf_a, "B": args.pdf_b},
            {"A": args.pdf_a_sha256, "B": args.pdf_b_sha256},
            owner_attests=args.owner_approves_abstract_pdf,
        )
        write_new_report(
            args.output.expanduser(),
            json.dumps(report, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n",
            Path.cwd().resolve(),
        )
    except (OSError, ValueError, PermissionError) as exc:
        parser.error(str(exc))
    counts = {}
    for item in report["cards"]:
        status = item["discrepancy_class"]
        counts[status] = counts.get(status, 0) + 1
    print(json.dumps({
        "kind": report["kind"], "cards": report["card_count"],
        "classes": dict(sorted(counts.items())),
        "scientifically_verified_claims": 0,
        "new_network_requests": 0,
        "memory_write": False,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
