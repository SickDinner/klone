"""Read-only measurement of overlap in a saved Council72 3-turn debate.

This is a lexical/role diversity screen, never scientific validation or
proof of independence between prompts, models, agents or sources.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

KIND = "klone-council72-adversarial-debate-v1"
STOP = frozenset(("että", "tämä", "tämän", "pitää", "täytyy", "sekä", "voidaan",
                   "ovat", "jos", "mutta", "vain", "sama", "saman", "tarkista",
                   "koko", "yksi", "myös", "mikä", "mistä", "jonka", "the",
                   "with", "from", "same", "and", "only", "into"))
WORDS = re.compile(r"[^\W\d_]{4,}", re.UNICODE)
MAX_FILE = 3_000_000

# Finnish/English topical screening cues; these are not semantic inference.
# Generic words such as "PDF" or "source" are deliberately not sufficient.
ISSUE_STEMS = {
    "source_version_identity": ("versio", "version", "arxiv-version", "tietueen"),
    "pdf_extraction_or_page_image": ("tekstikerro", "sivukuv", "poimin", "extraction", "extract"),
    "quote_or_meaning_match": ("sanatark", "vastine", "tekstivastaav", "osuma", "katkelma", "parafraas", "exact match"),
    "numeric_context": ("rmse", "lukuarv", "numeroväit", "numeroarv", "mittari", "metriik"),
    "scientific_methods": ("menetelm", "laskennan", "tuloksen pätev", "methodolog", "validit", "replicat"),
    "scope_or_generalization": ("yleist", "otoksen edustav", "generaliz", "sampling"),
    "inspection_coverage": ("kattav", "coverage"),
}


def _axes_in_text(text):
    # Keyword coverage is not semantic entailment or factual grounding.
    value = text.casefold()
    return {axis for axis, stems in ISSUE_STEMS.items()
            if any(stem in value for stem in stems)}


def _issue_axes(arg):
    return set().union(*(_axes_in_text(arg[field]) for field in
                         ("claim", "challenge_or_defense", "falsification_test")))


def _axis_evidence(arguments):
    """Show which bounded argument fields contain each screening cue.

    Card IDs are references cited by the argument, not validated evidence.
    """
    evidence = {}
    for idx, arg in enumerate(arguments, 1):
        for field in ("claim", "challenge_or_defense", "falsification_test"):
            for axis in sorted(_axes_in_text(arg[field])):
                evidence.setdefault(axis, []).append({
                    "argument_index": idx, "field": field,
                    "source_card_ids": list(arg["source_card_ids"])
                })
    return {axis: evidence[axis] for axis in sorted(evidence)}



def _fingerprint(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False)
    return sha256(raw.encode("utf-8")).hexdigest()


def _terms(text):
    return set(WORDS.findall(text.casefold())) - STOP


def _jaccard(left, right):
    union = left | right
    return round(len(left & right) / len(union), 3) if union else 0.0


def _text(value, name, limit=1200):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("invalid " + name)
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError("control character in " + name)
    return value


def _argument(record):
    if not isinstance(record, dict):
        raise ValueError("invalid argument")
    for key in ("claim", "challenge_or_defense", "falsification_test"):
        _text(record.get(key), key)
    ids = record.get("source_card_ids")
    if (not isinstance(ids, list) or len(ids) > 20 or
            any(not isinstance(v, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", v) for v in ids) or
            len(ids) != len(set(ids))):
        raise ValueError("invalid source card IDs")
    return record


def _turn(record, stance):
    if (not isinstance(record, dict) or record.get("stage") != stance
            or not isinstance(record.get("answer"), dict)):
        raise ValueError("missing debate stage")
    answer = record["answer"]
    if answer.get("stance") != stance:
        raise ValueError("debate stance does not match stage")
    ids = answer.get("role_focus_ids")
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 16
            or any(type(i) is not int or i not in range(1, 73) for i in ids)
            or len(ids) != len(set(ids))):
        raise ValueError("invalid Council72 role IDs")
    arguments = answer.get("arguments")
    if not isinstance(arguments, list) or not 1 <= len(arguments) <= 6:
        raise ValueError("invalid debate argument count")
    for arg in arguments:
        _argument(arg)
    return ids, arguments


def analyze(report):
    if not isinstance(report, dict):
        raise ValueError("expected a debate report")
    if (report.get("kind") != KIND or report.get("schema_version") != 1
            or report.get("mode") != "three_turn_debate_completed"
            or report.get("owner_review_required") is not True
            or report.get("scientific_truth_verified") is not False
            or report.get("memory_write") is not False):
        raise ValueError("not a bounded completed debate")
    expected = report.get("report_sha256")
    if (not isinstance(expected, str) or
            not re.fullmatch(r"[a-f0-9]{64}", expected) or
            expected != _fingerprint({k: v for k, v in report.items() if k != "report_sha256"})):
        raise ValueError("report content hash mismatch")
    counts = [report.get("model_api_requests_performed"), report.get("model_api_responses_reused")]
    if any(type(n) is not int or not 0 <= n <= 3 for n in counts) or sum(counts) != 3:
        raise ValueError("invalid model call counters")
    turns = report.get("debate_turns")
    if not isinstance(turns, list) or len(turns) != 3:
        raise ValueError("three debate stages required")
    left_roles, left_args = _turn(turns[0], "cross_examination")
    right_roles, right_args = _turn(turns[1], "defense")
    referee = turns[2]
    if (not isinstance(referee, dict) or referee.get("stage") != "arbiter"
            or not isinstance(referee.get("answer"), dict)):
        raise ValueError("missing arbiter")
    decision = referee["answer"]
    if decision.get("decision") != "owner_review_required":
        raise ValueError("arbiter authority boundary mismatch")
    if not isinstance(decision.get("falsifiable_next_tests"), list) or len(decision["falsifiable_next_tests"]) > 8:
        raise ValueError("invalid arbiter tests")
    final_tests = [_text(x, "arbiter test") for x in decision["falsifiable_next_tests"]]
    left_sources = {card for a in left_args for card in a["source_card_ids"]}
    right_sources = {card for a in right_args for card in a["source_card_ids"]}
    left_tests = [_terms(a["falsification_test"]) for a in left_args]
    right_tests = [_terms(a["falsification_test"]) for a in right_args]
    similarities = [max((_jaccard(a, b) for b in right_tests), default=0.0) for a in left_tests]
    all_prior = left_tests + right_tests
    arbiter_sim = [max((_jaccard(_terms(test), t) for t in all_prior), default=0.0)
                   for test in final_tests]
    role_overlap = _jaccard(set(left_roles), set(right_roles))
    card_overlap = _jaccard(left_sources, right_sources)
    left_axis_evidence = _axis_evidence(left_args)
    right_axis_evidence = _axis_evidence(right_args)
    left_axes = set(left_axis_evidence)
    right_axes = set(right_axis_evidence)
    right_new_axes = sorted(right_axes - left_axes)
    right_test_axes = set().union(*(_axes_in_text(a["falsification_test"])
                                     for a in right_args))
    right_new_axes_in_tests = sorted(set(right_new_axes) & right_test_axes)
    right_new_axes_outside_tests = sorted(set(right_new_axes) - right_test_axes)
    issue_overlap = _jaccard(left_axes, right_axes)
    flags = []
    if role_overlap == 1.0:
        flags.append("same_focal_role_set")
    elif role_overlap >= 0.8:
        flags.append("high_focal_role_overlap")
    if card_overlap == 1.0 and left_sources:
        flags.append("same_source_card_set")
    if issue_overlap >= 0.75 and len(left_axes & right_axes) >= 2:
        flags.append("shared_issue_axes_candidate")
    if any(x >= 0.6 for x in similarities):
        flags.append("similar_falsification_tests_candidate")
    if any(x >= 0.6 for x in arbiter_sim):
        flags.append("arbiter_test_repetition_candidate")
    flags.append("single_model_family_not_independent_consensus")
    return {
        "kind": "klone-council72-debate-diversity-audit-v1",
        "source_report_sha256": expected,
        "source_trust": "local_self_hash_only_not_authenticated",
        "model_api_requests_performed_by_this_audit": 0,
        "new_calls_reported_by_source": counts[0],
        "reused_calls_reported_by_source": counts[1],
        "memory_write": False, "scientific_truth_verified": False,
        "independent_models_verified": False, "owner_review_required": True,
        "cross_examiner_roles": left_roles, "defender_roles": right_roles,
        "shared_role_ids": sorted(set(left_roles) & set(right_roles)),
        "role_overlap_jaccard": role_overlap,
        "cross_examiner_source_cards": len(left_sources),
        "defender_source_cards": len(right_sources),
        "shared_source_cards": len(left_sources & right_sources),
        "source_card_overlap_jaccard": card_overlap,
        "cross_examiner_issue_axes": sorted(left_axes),
        "defender_issue_axes": sorted(right_axes),
        "shared_issue_axes": sorted(left_axes & right_axes),
        "issue_axis_overlap_jaccard": issue_overlap,
        "unmatched_defender_issue_axes": right_new_axes,
        "cross_examiner_axis_evidence": left_axis_evidence,
        "defender_axis_evidence": right_axis_evidence,
        "defender_new_axes_in_falsification_tests": right_new_axes_in_tests,
        "defender_new_axes_only_outside_falsification_tests": right_new_axes_outside_tests,
        "falsification_test_similarity_max_per_cross_argument": similarities,
        "arbiter_test_similarity_max_to_prior": arbiter_sim,
        "screening_flags": flags,
        "interpretation": "Word-stem issue axes and field locations are screening hints, not semantic proof, scientific validation, or evidence that a mentioned axis has a falsifiable test. Input self-hash is not publisher authentication."
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Council72-väittelyn offline-päällekkäisyystarkistus")
    parser.add_argument("report", type=Path, help="Paikallinen council72-quality-debate-live-*.json")
    parser.add_argument("--text", action="store_true")
    args = parser.parse_args(argv)
    try:
        p = args.report.expanduser()
        if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_FILE:
            raise ValueError("regular bounded non-symlink JSON file required")
        result = analyze(json.loads(p.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Debate audit refused input: {exc}\n")
    if args.text:
        print("KLONE 72 – väittelyn erojen tarkistus (ei uusia GPT-kutsuja)")
        print("Jaetut asiantuntijaroolit:", result["shared_role_ids"])
        print("Roolien Jaccard-päällekkäisyys:", result["role_overlap_jaccard"])
        print("Lähdekorttien päällekkäisyys:", result["source_card_overlap_jaccard"])
        print("Aiheakselit, haastaja:", ", ".join(result["cross_examiner_issue_axes"]) or "ei tunnistettu")
        print("Aiheakselit, puolustaja:", ", ".join(result["defender_issue_axes"]) or "ei tunnistettu")
        print("Aiheakseleiden Jaccard:", result["issue_axis_overlap_jaccard"])
        print("Puolustajan uudet aiheakselit:", result["unmatched_defender_issue_axes"])
        print("Uudet aiheakselit myös puolustajan testiehdotuksissa:",
              result["defender_new_axes_in_falsification_tests"])
        print("Uudet aiheakselit vain väitteessä/perustelussa:",
              result["defender_new_axes_only_outside_falsification_tests"])
        for axis in result["unmatched_defender_issue_axes"]:
            refs = result["defender_axis_evidence"][axis]
            print("Aiheen sijainnit", axis + ":",
                  ", ".join(f"argumentti {ref['argument_index']} / {ref['field']}" for ref in refs))
        print("Koeteltavien testien sanastolliset samankaltaisuudet:",
              result["falsification_test_similarity_max_per_cross_argument"])
        print("Ratkaisijan jatkotestien samankaltaisuudet:",
              result["arbiter_test_similarity_max_to_prior"])
        print("Tarkistusliput:", ", ".join(result["screening_flags"]))
        print("Tämä on sanastollinen tarkistus, EI tieteellisen riippumattomuuden todistus.")
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
