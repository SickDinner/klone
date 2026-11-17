"""KLONE E11.10: local PDF SHA and per-page evidence localization.

Bounded offline forensic aid. Replays E11.9 from canonical E11.1-E11.8
sources and compares the same local text extracted from owner-supplied PDF.
Never asserts publisher authentication or scientific truth. No network,
agent calls, Council72 votes or Memory Core writes.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import unicodedata

from .evidence_io import json_object, write_new_report
from .limbo_council_workbench import _fingerprint
from .limbo_evidence_cards import _measures
from .limbo_evidence_review import MAX_MANIFEST_BYTES, _read_input
from .limbo_fulltext_review import (
    MAX_SOURCE_BYTES, _read_source, _spans, review_fulltexts,
)

MAX_PDF_BYTES = 15_000_000
MAX_PAGES = 160
MAX_PDF_TEXT_OUTPUT = MAX_SOURCE_BYTES + 1024
MAX_PAGE_MATCHES = 5
HEX_SHA256 = re.compile(r"^[a-f0-9]{64}$")
PAGES_LINE = re.compile(r"^Pages:\s*(\d+)\s*$", re.M)
TOKENS = re.compile(r"[^\W_]{4,}", re.UNICODE)


def _normalize(text: str) -> str:
    """Only match spelling/typography, not the meaning of sentences."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00ad", "")
    text = re.sub(r"(?<=\w)-[ \t]*\r?\n[ \t]*(?=\w)", "", text)
    return " ".join(text.casefold().split())


def _execute(command: list[str], *, limit: int) -> bytes:
    try:
        done = subprocess.run(
            command, stdin=subprocess.DEVNULL, capture_output=True,
            timeout=35, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("bounded local PDF utility failed") from exc
    if done.returncode or len(done.stdout) > limit:
        raise ValueError("PDF extraction failed, returned error or exceeded limit")
    return done.stdout


def _pages(path: Path) -> list[str]:
    info = _execute(["pdfinfo", str(path)], limit=100_000)
    try:
        found = PAGES_LINE.search(info.decode("utf-8"))
    except UnicodeError as exc:
        raise ValueError("invalid PDF metadata encoding") from exc
    if found is None or not 1 <= int(found.group(1)) <= MAX_PAGES:
        raise ValueError("PDF page count missing or exceeds limit")
    count = int(found.group(1))
    pages = []
    total_chars = 0
    for page_no in range(1, count + 1):
        raw = _execute([
            "pdftotext", "-layout", "-enc", "UTF-8",
            "-f", str(page_no), "-l", str(page_no),
            str(path), "-",
        ], limit=MAX_PDF_TEXT_OUTPUT)
        try:
            page = raw.decode("utf-8-sig")
        except UnicodeError as exc:
            raise ValueError("non-UTF-8 extracted PDF page") from exc
        total_chars += len(page)
        if total_chars > 2_500_000:
            raise ValueError("excessive PDF page text")
        pages.append(page)
    return pages


def _candidate_pages(pages: list[str], quote: str) -> list[dict]:
    words = set(TOKENS.findall(_normalize(quote)))
    if not words:
        return []
    possible = []
    for page_num, page in enumerate(pages, 1):
        page_words = set(TOKENS.findall(_normalize(page)))
        count = len(words & page_words)
        if count:
            possible.append({
                "page": page_num,
                "shared_distinct_tokens": count,
                "query_distinct_tokens": len(words),
                "not_evidence": True,
            })
    return sorted(possible, key=lambda row: (-row["shared_distinct_tokens"],
                                              row["page"]))[:3]


def inspect_pdfs(core_db, original, proposals, selected, ledger, quality,
                 queue, receipt, comparison, cards, fulltext, text_inputs,
                 pdf_paths, expected_pdf_sha256, *, owner_attests=False):
    """All source identities and the E11.9 local text are revalidated."""
    if owner_attests is not True:
        raise ValueError("explicit owner PDF review consent required")
    if (type(pdf_paths) is not dict or set(pdf_paths) != {"A", "B"} or
        type(text_inputs) is not dict or set(text_inputs) != {"A", "B"} or
        type(expected_pdf_sha256) is not dict or set(expected_pdf_sha256) != {"A", "B"}):
        raise ValueError("two PDF and local text roles required")
    if type(fulltext) is not dict or type(fulltext.get("sources")) is not dict:
        raise ValueError("E11.9 report required")
    for role in ("A", "B"):
        if (type(expected_pdf_sha256[role]) is not str or
            HEX_SHA256.fullmatch(expected_pdf_sha256[role]) is None):
            raise ValueError("expected PDF SHA-256 required for each role")
        if type(fulltext["sources"].get(role)) is not dict:
            raise ValueError("E11.9 source role missing")
    ids = {r: fulltext["sources"][r].get("arxiv_id") for r in ("A", "B")}
    rights = {r: fulltext["sources"][r].get("usage_rights_note")
              for r in ("A", "B")}
    fresh = review_fulltexts(
        core_db, original, proposals, selected, ledger, quality, queue,
        receipt, comparison, cards, text_inputs,
        declared_ids=ids, rights_notes=rights, owner_attests=True,
    )
    if (fulltext != fresh or
        fulltext.get("report_sha256") != _fingerprint({
            k: v for k, v in fulltext.items() if k != "report_sha256"
        })):
        raise ValueError("E11.9 source report stale or altered")

    pdf_pages = {}
    pdf_meta = {}
    for role in ("A", "B"):
        path = Path(pdf_paths[role]).expanduser()
        data = _read_input(path, MAX_PDF_BYTES, "E11.10-pdf-" + role)
        if (not data.startswith(b"%PDF-") or b"%%EOF" not in data[-4096:]):
            raise ValueError("not a bounded complete PDF source")
        digest = sha256(data).hexdigest()
        if digest != expected_pdf_sha256[role]:
            raise ValueError("PDF SHA-256 does not match explicit owner expectation")
        complete = _execute([
            "pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"
        ], limit=MAX_PDF_TEXT_OUTPUT)
        normalized_text = _read_source(complete, role)
        extracted_sha = sha256(normalized_text.encode("utf-8")).hexdigest()
        if extracted_sha != fresh["sources"][role]["text_sha256"]:
            raise ValueError("PDF extraction not identical to E11.9 local text")
        pages = _pages(path)
        pdf_pages[role] = pages
        pdf_meta[role] = {
            "arxiv_id": ids[role],
            "pdf_sha256": digest,
            "pdf_bytes": len(data),
            "page_count": len(pages),
            "extracted_text_sha256": extracted_sha,
            "text_identical_to_e11_9": True,
            "source_event_id": fresh["sources"][role]["source_event_id"],
            "local_pdf_not_publisher_authenticated": True,
        }

    located = []
    for old in fresh["cards"]:
        role = old["source"]
        card_id = old["candidate_id"]
        quote = next(c["local_summary_quote"] for c in cards["cards"]
                     if c["candidate_id"] == card_id and c["source"] == role)
        found_exact = []
        found_normalized = []
        numeric_pages = []
        for n, page in enumerate(pdf_pages[role], 1):
            for span in _spans(page, quote):
                if len(found_exact) < MAX_PAGE_MATCHES:
                    found_exact.append({"page": n, **span})
            nq = _normalize(quote)
            np = _normalize(page)
            start = np.find(nq) if nq else -1
            if start >= 0 and len(found_normalized) < MAX_PAGE_MATCHES:
                found_normalized.append({
                    "page": n,
                    "page_normalized_char_start": start,
                    "page_normalized_char_end": start + len(nq),
                })
            relevant = {
                (x["number"], x["unit"])
                for x in old["unit_aware_numeric_mentions"]
            }
            same = [
                x for x in _measures(page)
                if (x["number"], x["unit"]) in relevant
            ]
            if same:
                numeric_pages.append({
                    "page": n,
                    "same_value_and_unit": [
                        {"number": x["number"], "unit": x["unit"],
                         "page_char_start": x["char_start"],
                         "page_char_end": x["char_end"]}
                        for x in same[:MAX_PAGE_MATCHES]
                    ]
                })
        status = ("literal_page_quote_unverified" if found_exact else
                  "typography_normalized_page_quote_unverified"
                  if found_normalized else
                  "numbers_on_pages_only_unverified" if numeric_pages else
                  "not_located_on_pdf_pages_not_disproved")
        located.append({
            "candidate_id": card_id,
            "source": role,
            "arxiv_id": old["arxiv_id"],
            "prior_full_text_lexical_class": old["full_text_lexical_class"],
            "page_locator_status": status,
            "literal_page_spans": found_exact,
            "normalized_page_spans": found_normalized,
            "numeric_page_mentions": numeric_pages[:MAX_PAGES],
            "candidate_pages_by_token_overlap_not_evidence":
                _candidate_pages(pdf_pages[role], quote),
            "scientific_claim_verified": False,
            "council_review_completed": False,
        })
    results = {
        "kind": "klone-e11-10-local-pdf-page-locator",
        "schema_version": 1,
        "e11_9_report_sha256": fresh["report_sha256"],
        "e11_8_report_sha256": fresh["e11_8_report_sha256"],
        "source_snapshot_sha256": fresh["source_snapshot_sha256"],
        "pdf_sources": pdf_meta,
        "card_count": len(located),
        "cards": located,
        "local_pdf_page_text_scanned": True,
        "arxiv_publisher_pdf_authenticated": False,
        "scientifically_verified_claims": 0,
        "council_reviews_performed": 0,
        "new_network_requests": 0,
        "memory_write": False,
        "authority": {
            "publisher_authentication": False,
            "scientific_truth": False,
            "autonomous_council_review": False,
            "council_votes": False,
            "memory_write": False,
            "network_actions": False,
        },
    }
    results["report_sha256"] = _fingerprint(results)
    return results


def main(argv=None):
    p = argparse.ArgumentParser(description="KLONE E11.10 offline local PDF page locator")
    p.add_argument("--klone-db", required=True, type=Path)
    for key in ("original", "proposals", "selected", "ledger", "quality",
                "queue", "receipt", "comparison", "cards", "fulltext"):
        p.add_argument("--" + key, type=Path, required=True)
    for role in ("a", "b"):
        p.add_argument("--pdf-" + role, type=Path, required=True)
        p.add_argument("--pdf-" + role + "-sha256", required=True)
        p.add_argument("--text-" + role, type=Path, required=True)
    p.add_argument("--owner-approves-local-pdf", action="store_true")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        docs = [
            json_object(_read_input(getattr(args, key),
                                    MAX_MANIFEST_BYTES, "E11.10-" + key))
            for key in ("original", "proposals", "selected", "ledger",
                        "quality", "queue", "receipt", "comparison", "cards",
                        "fulltext")
        ]
        input_texts = {
            role: _read_input(getattr(args, "text_" + role.lower()),
                              MAX_SOURCE_BYTES, "E11.10-text-" + role)
            for role in ("A", "B")
        }
        report = inspect_pdfs(
            args.klone_db, *docs, input_texts,
            {"A": args.pdf_a, "B": args.pdf_b},
            {"A": args.pdf_a_sha256, "B": args.pdf_b_sha256},
            owner_attests=args.owner_approves_local_pdf,
        )
        write_new_report(
            args.output.expanduser(),
            json.dumps(report, ensure_ascii=False, indent=2,
                       allow_nan=False) + "\n", Path.cwd().resolve(),
        )
    except (OSError, ValueError, PermissionError) as exc:
        p.error(str(exc))
    print(json.dumps({
        "kind": report["kind"], "cards": report["card_count"],
        "sources": len(report["pdf_sources"]),
        "scientific_claims_verified": False, "memory_write": False,
        "new_network_requests": 0, "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
