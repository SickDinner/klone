"""KLONE E11.9: offline, version-bound lexical inspection of owner-supplied full text.

No PDF fetching, model inference, scientific approval, Council72 execution,
service restart or Memory Core writes.  Text supplied by an owner is NOT
publisher-authenticated: only a licensed original can establish provenance.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

from .evidence_io import json_object, write_new_report
from .limbo_arxiv_primary import ARXIV_ID
from .limbo_council_workbench import _fingerprint
from .limbo_evidence_cards import MAX_CARDS, _measures, build_cards
from .limbo_evidence_review import MAX_MANIFEST_BYTES, _read_input

MAX_SOURCE_BYTES = 2 * 1024 * 1024
MIN_SOURCE_CHARS = 200
MAX_SOURCE_CHARS = 1_000_000
MAX_MATCH_SPANS = 5


def _read_source(raw: bytes, label: str) -> str:
    if type(raw) is not bytes or not raw or len(raw) > MAX_SOURCE_BYTES:
        raise ValueError(f"{label}: invalid or oversized UTF-8 text")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError(f"{label}: source must be UTF-8 plain text") from exc
    if not MIN_SOURCE_CHARS <= len(content) <= MAX_SOURCE_CHARS:
        raise ValueError(f"{label}: source text length outside bounds")
    if ("\\x00" in content or content.lstrip().startswith("%PDF") or
        re.match(r"\\s*<(?:!doctype\\s+html|html)[\\s>]", content, re.I)):
        raise ValueError(f"{label}: plain-text source required (not PDF/HTML)")
    return content


def _spans(source: str, quote: str) -> list[dict]:
    if type(quote) is not str or not 12 <= len(quote) <= 400 or not quote.strip():
        raise ValueError("invalid source card quote")
    # Whitespace-insensitive lexical match, not a semantic translation.
    pattern = re.compile(r"\\s+".join(re.escape(piece) for piece in quote.split()),
                         re.IGNORECASE)
    found = []
    for match in pattern.finditer(source):
        found.append({"char_start": match.start(), "char_end": match.end()})
        if len(found) == MAX_MATCH_SPANS:
            break
    return found


def review_fulltexts(core_db, original, proposals, selected, ledger, quality,
                     queue, receipt, comparison, cards_report, sources, *,
                     declared_ids, rights_notes, owner_attests=False):
    """Rebuild the E11.8 evidence chain before using any alleged full text."""
    if owner_attests is not True:
        raise ValueError("explicit owner confirmation of supplied local text required")
    if (type(sources) is not dict or set(sources) != {"A", "B"} or
        type(declared_ids) is not dict or set(declared_ids) != {"A", "B"} or
        type(rights_notes) is not dict or set(rights_notes) != {"A", "B"}):
        raise ValueError("exactly two source roles A and B required")
    if any(type(rights_notes[k]) is not str or not 5 <= len(rights_notes[k]) <= 240
           for k in ("A", "B")):
        raise ValueError("explicit bounded usage-rights notes required")
    if any(type(declared_ids[k]) is not str or not ARXIV_ID.fullmatch(declared_ids[k])
           for k in ("A", "B")):
        raise ValueError("explicit versioned arXiv IDs required")
    if declared_ids["A"] == declared_ids["B"]:
        raise ValueError("sources must be two distinct versioned publications")
    if type(cards_report) is not dict:
        raise ValueError("E11.8 report object required")

    expected = build_cards(core_db, original, proposals, selected, ledger,
                           quality, queue, receipt, comparison)
    if (cards_report != expected or
        cards_report.get("report_sha256") != _fingerprint({
            key: value for key, value in cards_report.items()
            if key != "report_sha256"
        })):
        raise ValueError("E11.8 report stale, tampered or from another source chain")

    event_ids = expected["source_event_ids"]
    if (type(event_ids) is not list or len(event_ids) != 2 or
        any(type(x) is not int for x in event_ids) or event_ids[0] == event_ids[1]):
        raise ValueError("expected two distinct canonical source events")
    records = expected["cards"]
    if (type(records) is not list or len(records) != expected["card_count"] or
        not 1 <= len(records) <= MAX_CARDS):
        raise ValueError("invalid E11.8 verification card count")

    text_by_role = {role: _read_source(sources[role], role) for role in ("A", "B")}
    digests = {role: sha256(text_by_role[role].encode("utf-8")).hexdigest()
               for role in ("A", "B")}
    if digests["A"] == digests["B"]:
        raise ValueError("two source roles cannot share identical full-text content")
    seen = set()
    for card in records:
        role = card["source"]
        if role not in ("A", "B"):
            raise ValueError("invalid card source role")
        if (card["source_event_id"] != event_ids[("A", "B").index(role)] or
            card["arxiv_id"] != declared_ids[role] or
            card["original_publication_url"] !=
                "https://arxiv.org/abs/" + declared_ids[role]):
            raise ValueError("source event, arXiv version or URL mismatch")
        ident = (card["candidate_id"], card["source_event_id"])
        if ident in seen:
            raise ValueError("duplicate source candidate")
        seen.add(ident)
    if set(card["source"] for card in records) != {"A", "B"}:
        raise ValueError("both source roles must have review cards")

    measures_by_role = {role: {
        (measure["number"], measure["unit"]): measure
        for measure in _measures(text_by_role[role])
    } for role in ("A", "B")}

    results = []
    for card in records:
        role = card["source"]
        spans = _spans(text_by_role[role], card["local_summary_quote"])
        matches = []
        for measure in card["measured_quantities_in_local_quote"]:
            target = measures_by_role[role].get((measure["number"], measure["unit"]))
            matches.append({
                "number": measure["number"], "unit": measure["unit"],
                "mentioned_with_same_unit": target is not None,
                "source_char_start": target["char_start"] if target else None,
                "source_char_end": target["char_end"] if target else None,
            })
        status = ("lexical_quote_found_unverified" if spans else
                  "unit_aware_numbers_only_unverified" if any(
                      m["mentioned_with_same_unit"] for m in matches) else
                  "not_located_in_supplied_full_text_not_disproved")
        results.append({
            "candidate_id": card["candidate_id"],
            "source": role,
            "source_event_id": card["source_event_id"],
            "arxiv_id": card["arxiv_id"],
            "local_quote_sha256": card["local_quote_sha256"],
            "supplied_text_sha256": digests[role],
            "priority": card["priority"],
            "full_text_lexical_class": status,
            "lexical_match_spans": spans,
            "unit_aware_numeric_mentions": matches,
            "scientific_claim_verified": False,
            "full_text_publisher_authenticated": False,
            "council_review_completed": False,
            "remaining_checks": [
                "Authenticate this extracted text against the pinned arXiv PDF/source.",
                "Read methods, study population, outcomes, baselines and uncertainty.",
                "Determine whether the quoted claim is supported in context.",
                "Check subsequent corrections and independent replication.",
            ],
        })
    report = {
        "kind": "klone-e11-9-owner-fulltext-lexical-review",
        "schema_version": 1,
        "e11_8_report_sha256": expected["report_sha256"],
        "source_snapshot_sha256": expected["source_snapshot_sha256"],
        "source_event_ids": event_ids,
        "sources": {
            role: {
                "arxiv_id": declared_ids[role],
                "source_event_id": event_ids[("A", "B").index(role)],
                "owner_supplied": True,
                "usage_rights_note": rights_notes[role],
                "text_sha256": digests[role],
                "text_chars": len(text_by_role[role]),
                "origin": "owner_supplied_plain_text_unverified_against_publisher",
                "publisher_authenticated": False,
            } for role in ("A", "B")
        },
        "card_count": len(results),
        "cards": results,
        "local_full_text_scanned": True,
        "original_arxiv_full_text_authenticated": False,
        "scientifically_verified_claims": 0,
        "council_reviews_performed": 0,
        "new_network_requests": 0,
        "memory_write": False,
        "authority": {
            "research_claim_verified": False,
            "council_votes": False,
            "autonomous_agent_execution": False,
            "memory_write": False,
            "network_access": False,
            "publisher_full_text_authenticated": False,
        },
    }
    report["report_sha256"] = _fingerprint(report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="KLONE E11.9 offline local full-text inspection")
    parser.add_argument("--klone-db", type=Path, required=True)
    for field in ("original", "proposals", "selected", "ledger", "quality",
                  "queue", "receipt", "comparison", "cards"):
        parser.add_argument("--" + field, type=Path, required=True)
    for role in ("a", "b"):
        parser.add_argument("--source-" + role + "-file", type=Path, required=True)
        parser.add_argument("--source-" + role + "-id", required=True)
        parser.add_argument("--rights-note-" + role, required=True)
    parser.add_argument("--owner-confirms-local-text", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        docs = [
            json_object(_read_input(getattr(args, field), MAX_MANIFEST_BYTES,
                                    "E11.9-" + field))
            for field in ("original", "proposals", "selected", "ledger",
                          "quality", "queue", "receipt", "comparison", "cards")
        ]
        supplied = {
            role: _read_input(getattr(args, "source_" + role.lower() + "_file"),
                              MAX_SOURCE_BYTES, "E11.9-" + role)
            for role in ("A", "B")
        }
        result = review_fulltexts(
            args.klone_db, *docs, supplied,
            declared_ids={"A": args.source_a_id, "B": args.source_b_id},
            rights_notes={"A": args.rights_note_a, "B": args.rights_note_b},
            owner_attests=args.owner_confirms_local_text,
        )
        write_new_report(args.output.expanduser(),
                         json.dumps(result, ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n",
                         Path.cwd().resolve())
    except (OSError, ValueError, PermissionError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "kind": result["kind"], "cards": result["card_count"],
        "scientifically_verified_claims": 0, "new_network_requests": 0,
        "memory_write": False, "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
