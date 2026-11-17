"""Council72 Quality Lab v1 — offline, read-only evaluation of a real 72-seat run.

Data contracts, source hashes, seat membership and citations are validated
before producing anything. All metrics are HEURISTICS, not semantic
verification, factual correctness scores, or proof of independent minds.
No network, model call, database write, system shell, or autonomous actions.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re

from .council72 import catalog
from .council72_intelligence_bridge import (
    ALLOWED_MODELS, CouncilModelError, MAX_EVIDENCE_CARDS,
    _council_roles, _fingerprinted_report, _founder_prompt, _request_digest,
    _role_prompt, _valid_ring_record, _validate_founders,
)
from .evidence_io import json_object, write_new_report
from .limbo_council_workbench import _fingerprint
from .limbo_evidence_review import _read_input, MAX_MANIFEST_BYTES

KIND = "klone-council72-quality-lab-v1"
STOPWORDS = frozenset((
    "että", "tämä", "tämän", "tässä", "sillä", "ovat", "olla", "voidaan", "myös",
    "mutta", "joita", "jonka", "joten", "kuten", "vain", "siinä", "koska",
    "eivät", "niin", "niiden", "eikä", "sekä", "tulee", "antaa", "tarkistaa",
    "aineisto", "lähde", "lähteet", "katkelmat", "väitteet", "väite",
    "the", "and", "for", "with", "from", "that", "this", "their", "they",
))
WORDS = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
# Numeric clues are screening heuristics, not verification.
NUMERIC_CLAIM = re.compile(
    r"(?<![0-9A-Za-z])\d+(?:[.,]\d+)?\s*(?:%|prosenttia|prosentin|kelviniä|kelvin|RMSE)",
    re.IGNORECASE,
)


def _load(path, name):
    return json_object(
        _read_input(Path(path).expanduser(), MAX_MANIFEST_BYTES, name)
    )


def _validate_bundle(report, dossier):
    cards = _fingerprinted_report(dossier)
    board, members = _council_roles()
    if type(report) is not dict:
        raise CouncilModelError("complete Council72 live report required")
    if (report.get("kind") != "klone-council72-intelligence-bridge-v1"
        or report.get("schema_version") != 1
        or report.get("mode") != "api_nine_model_calls_completed"
        or report.get("report_sha256") != _fingerprint({
            key: value for key, value in report.items()
            if key != "report_sha256"
        })):
        raise CouncilModelError("incorrect or modified Council72 live report")
    if (report.get("e11_11_report_sha256") != dossier["report_sha256"]
        or report.get("catalog_sha256") != _fingerprint(board)
        or report.get("model") not in ALLOWED_MODELS
        or type(report.get("question")) is not str
        or not 8 <= len(report["question"].strip()) <= 1000
        or report.get("scientific_truth_verified") is not False
        or report.get("sources_authenticated_by_publisher") is not False
        or report.get("memory_write") is not False
        or report.get("council_binding_votes") != 0
        or report.get("owner_review_required") is not True
        or report.get("real_independent_72_llm_agents") is not False
        or report.get("ring_model_calls") != 8
        or report.get("founder_model_calls") != 1
        or report.get("seat_count") != 72):
        raise CouncilModelError("Council72 report/source/authority mismatch")
    if (type(report.get("ring_calls")) is not list
        or len(report["ring_calls"]) != 8
        or type(report.get("founder_synthesis")) is not dict):
        raise CouncilModelError("full eight-ring and founder run required")
    allowed = {card["card_id"] for card in cards}
    for ring, record in zip(board["rings"][:8], report["ring_calls"]):
        pair = _role_prompt(report["question"], cards, ring, members)
        _valid_ring_record(record, ring, pair, members, allowed)
    founder = report["founder_synthesis"]
    _validate_founders(founder, board["founder_ids"], allowed)
    prompt = _founder_prompt(
        report["question"], cards,
        [r["eight_seat_assessments"] for r in report["ring_calls"]],
        board, members
    )
    if report.get("founder_request_sha256") != _request_digest(*prompt):
        raise CouncilModelError("founders summary request SHA mismatch")
    if (type(report.get("founder_api_response_id")) is not str
        or len(report["founder_api_response_id"]) > 128):
        raise CouncilModelError("invalid founders response ID")
    if report.get("model_analyses_total", 9) != 9:
        raise CouncilModelError("expected exactly nine model analyses")
    if (
        type(report.get("model_api_requests_performed")) is not int
        or not 0 <= report["model_api_requests_performed"] <= 9
        or type(report.get("model_api_requests_reused", 0)) is not int
        or report["model_api_requests_performed"]
             + report.get("model_api_requests_reused", 0) != 9
    ):
        raise CouncilModelError("model call accounting mismatch")
    return cards, board, members


def _terms(value):
    return {
        w for w in WORDS.findall(value.lower())
        if w not in STOPWORDS
    }


def _jaccard(a, b):
    x, y = _terms(a), _terms(b)
    return round(len(x & y) / len(x | y), 4) if (x | y) else 0.0


def _numeric_matches(text):
    return sorted(set(
        re.sub(r"\s+", "", m.group(0)).lower().replace(",", ".")
        for m in NUMERIC_CLAIM.finditer(text)
    ))


def quality_assessment(report, dossier):
    cards, board, members = _validate_bundle(report, dossier)
    source_text = " ".join(card["excerpt_untrusted"] for card in cards)
    known_numbers = set(_numeric_matches(source_text))
    seats = []
    ring_quality = []
    overlap = []
    cited = set()
    for ring, record in zip(board["rings"][:8], report["ring_calls"]):
        value = record["eight_seat_assessments"]
        ring_citations = value["evidence_card_ids"]
        cited.update(ring_citations)
        role_texts = []
        for seat in value["seat_assessments"]:
            mid = seat["member_id"]
            member = members[mid]
            prose = seat["observation"] + "\n" + seat["challenge"]
            signals = _numeric_matches(prose)
            new_number_signals = [v for v in signals if v not in known_numbers]
            role_texts.append((mid, prose))
            seats.append({
                "member_id": mid,
                "member_name": member["name"],
                "ring_id": ring["id"],
                "ring_domain": ring["domain"],
                "specialist_task": member["task"],
                "observation": seat["observation"],
                "challenge": seat["challenge"],
                "task_lexical_alignment": _jaccard(
                    member["task"], prose
                ),
                "evidence_ids_at_ring_level": ring_citations,
                "numeric_signals_not_in_source_excerpts": new_number_signals,
                "citations_attached_to_individual_seat": False,
            })
        for i, (a, a_text) in enumerate(role_texts):
            for b, b_text in role_texts[i + 1:]:
                similarity = _jaccard(a_text, b_text)
                if similarity >= 0.5:
                    overlap.append({
                        "member_a": a, "member_b": b,
                        "ring_id": ring["id"],
                        "lexical_jaccard": similarity,
                        "is_semantic_duplication_proven": False,
                    })
        ring_quality.append({
            "ring_id": ring["id"],
            "domain": ring["domain"],
            "member_count": len(role_texts),
            "finding_count": len(value["findings"]),
            "counterargument_count": len(value["counterarguments"]),
            "open_question_count": len(value["open_questions"]),
            "ring_citation_count": len(ring_citations),
            "cited_cards": ring_citations,
            "uncertainty_note": value["uncertainty_note"],
        })
    founder = report["founder_synthesis"]
    cited.update(founder["evidence_card_ids"])
    founder_positions = [{
        "member_id": row["member_id"],
        "name": members[row["member_id"]]["name"],
        "stewards_ring": members[row["member_id"]]["stewards_ring"],
        "position": row["position"],
        "reason": row["reason"],
    } for row in founder["founder_positions"]]
    all_card_ids = {c["card_id"] for c in cards}
    response = {
        "kind": KIND, "schema_version": 1, "mode": "offline_quality_audit",
        "input_report_sha256": report["report_sha256"],
        "e11_11_report_sha256": dossier["report_sha256"],
        "model": report["model"], "question": report["question"],
        "ring_count": 8, "founder_count": 8,
        "role_count": len(seats) + len(founder_positions),
        "role_assessments": seats,
        "ring_diagnostics": ring_quality,
        "founder_positions": founder_positions,
        "founder_synthesis": founder["synthesis"],
        "explicit_founder_disagreements": founder["disagreements"],
        "founder_next_experiments": founder["next_experiments"],
        "citation_coverage": {
            "total_source_cards": len(all_card_ids),
            "cited_unique_cards": len(cited),
            "unused_card_ids": sorted(all_card_ids - cited),
            "source_card_ids_validated": True,
            "per_claim_source_authentication": False,
        },
        "likely_lexical_overlaps": sorted(
            overlap, key=lambda row: row["lexical_jaccard"], reverse=True
        )[:30],
        "heuristic_notes": [
            "Lexical overlap only measures shared non-stopword tokens, not semantic duplication.",
            "Task lexical alignment measures shared words, not true specialist skill.",
            "New numeric signals are review candidates, NOT confirmed hallucinations.",
            "A matching citation ID proves only local membership of the supplied source packet.",
            "The source packet has NOT been independently verified against publisher originals.",
            "Founder disagreements are quoted from the model, not independently inferred.",
        ],
        "scientific_truth_verified": False,
        "owner_review_required": True,
        "memory_write": False,
        "model_api_requests_performed": 0,
        "external_tools_executed": 0,
    }
    response["report_sha256"] = _fingerprint(response)
    return response


def evidence_tool(dossier, tool, *, card_id=None, member_id=None):
    """A fixed, auditable, LOCAL read-only tool boundary for public packets.

    No endpoint strings, arbitrary filesystem paths, SQL, Python evaluation
    or uncontrolled network calls are accepted by this dispatcher.
    """
    cards = _fingerprinted_report(dossier)
    board, members = _council_roles()
    allowed = ("card_lookup", "discrepancy_counts", "member_profile")
    if tool not in allowed:
        raise PermissionError("non-allowlisted tool denied")
    if tool == "card_lookup":
        if type(card_id) is not str:
            raise ValueError("card ID required")
        found = [c for c in cards if c["card_id"] == card_id]
        if len(found) != 1:
            raise ValueError("card not found in approved public packet")
        result = {"card": found[0]}
    elif tool == "member_profile":
        if type(member_id) is not int or member_id not in members:
            raise ValueError("canonical Council72 member ID required")
        member = members[member_id]
        result = {
            "member_id": member_id, "name": member["name"],
            "ring": member["ring"], "task": member["task"],
            "traits": member["traits"],
            "founder": member["founder"],
        }
    else:
        result = {"classes": dict(sorted(Counter(
            card["discrepancy"] for card in cards
        ).items())), "card_count": len(cards)}
    answer = {
        "kind": "klone-council72-public-tool-result-v1",
        "tool": tool, "source_report_sha256": dossier["report_sha256"],
        "result": result, "network_request_count": 0, "memory_write": False,
        "read_only": True, "owner_review_required": True,
    }
    answer["report_sha256"] = _fingerprint(answer)
    return answer


def debate_preview(report, dossier):
    audit = quality_assessment(report, dossier)
    cards = _fingerprinted_report(dossier)
    roles = audit["role_assessments"]
    rings = audit["ring_diagnostics"]
    founder_disagreements = audit["explicit_founder_disagreements"]
    debate_axes = []
    for ring in rings:
        debate_axes.append({
            "ring_id": ring["ring_id"],
            "domain": ring["domain"],
            "speaking_member_ids": [
                x["member_id"] for x in roles
                if x["ring_id"] == ring["ring_id"]
            ],
            "provisional_question": (
                "Mikä tämän ringin vahvin väite on, ja mikä havainto "
                "osoittaisi sen vääräksi?"
            ),
            "citations_that_need_direct_check": ring["cited_cards"],
        })
    packet = {
        "kind": "klone-council72-debate-preview-v1",
        "schema_version": 1,
        "mode": "offline_no_model_calls",
        "question": report["question"],
        "input_report_sha256": report["report_sha256"],
        "input_e11_sha256": dossier["report_sha256"],
        "model": report["model"],
        "role_specialist_topics": [
            {"member_id": m["member_id"], "ring_id": m["ring_id"],
             "assigned_task": m["specialist_task"]}
            for m in roles
        ],
        "eight_ring_debate_axes": debate_axes,
        "founder_explicit_disagreements": founder_disagreements,
        "source_cards_unverified": cards,
        "three_model_turns_if_separately_authorized": [
            "cross_examiner", "defender", "neutral_arbiter"
        ],
        "tools_available_read_only": [
            "card_lookup", "discrepancy_counts", "member_profile"
        ],
        "new_paid_requests": 0, "memory_write": False,
        "binding_votes": 0, "source_truth_verified": False,
    }
    packet["report_sha256"] = _fingerprint(packet)
    return packet


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Council72 offline 72-seat audit, adversarial debate preview, local evidence tools"
    )
    parser.add_argument("--report", type=Path,
                        help="the complete 72-role Council72 live JSON")
    parser.add_argument("--evidence", type=Path, required=True,
                        help="original public E11.11 JSON evidence")
    parser.add_argument("--mode", required=True, choices=(
        "assess", "debate-preview", "tool"
    ))
    parser.add_argument("--tool", choices=(
        "card_lookup", "discrepancy_counts", "member_profile"
    ))
    parser.add_argument("--card-id")
    parser.add_argument("--member-id", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        dossier = _load(args.evidence, "public E11.11")
        if args.mode == "tool":
            if not args.tool:
                raise ValueError("tool name required")
            answer = evidence_tool(dossier, args.tool, card_id=args.card_id,
                                   member_id=args.member_id)
        else:
            if args.report is None:
                raise ValueError("complete live report required")
            report = _load(args.report, "Council72 live report")
            answer = (quality_assessment(report, dossier)
                      if args.mode == "assess"
                      else debate_preview(report, dossier))
        write_new_report(
            args.output.expanduser(),
            json.dumps(answer, ensure_ascii=False, indent=2,
                       allow_nan=False) + "\n",
            Path.cwd().resolve()
        )
    except (OSError, ValueError, PermissionError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "kind": answer["kind"], "mode": args.mode,
        "api_requests": 0, "memory_write": False,
        "output": str(args.output.expanduser()),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
