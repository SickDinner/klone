"""Draft-only source receipt. Pure functions, no authority or IO.

The trusted issuer must independently authenticate its caller, enforce room
policy, provision the secret, and authenticate research-source provenance.
Neither a signed receipt nor a human approval proves a scientific claim.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re


class EvidenceError(ValueError):
    pass


SUBJECT_KEYS = frozenset((
    "domain", "action", "classification", "room_id", "proposal_id",
    "target_version", "draft_sha256", "debate_sha256", "dossier_sha256",
    "card_ids", "distinct_origin_events", "distinct_arxiv_works",
    "independent_sources_verified", "scientific_claim_verified",
))


def _check_subject_scope(subject):
    if (type(subject) is not dict or set(subject) != SUBJECT_KEYS
            or subject.get("domain") != "klone-evidence-receipt-subject-v1"
            or subject.get("action") != "draft_unverified"
            or subject.get("classification") != "public"
            or subject.get("room_id") != "public-room"
            or subject.get("independent_sources_verified") is not False
            or subject.get("scientific_claim_verified") is not False):
        raise EvidenceError("invalid_claim_scope")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _report_hash(record):
    if type(record) is not dict or type(record.get("report_sha256")) is not str:
        raise EvidenceError("invalid_report")
    actual = digest({k: v for k, v in record.items() if k != "report_sha256"})
    if not hmac.compare_digest(record["report_sha256"], actual):
        raise EvidenceError("report_integrity_failure")
    return actual


def make_subject(*, proposal_id, target_version, draft_text, ids, debate, dossier):
    """Bind a *public unverified draft* to exact report hashes and content."""
    if any(type(x) is not str or not x or len(x) > 128
           for x in (proposal_id, target_version)):
        raise EvidenceError("invalid_proposal_identity")
    if type(draft_text) is not str or not draft_text.strip() or len(draft_text) > 2000:
        raise EvidenceError("invalid_draft")
    if type(ids) is not list or not 1 <= len(ids) <= 64 or any(
            type(x) is not str or not x for x in ids):
        raise EvidenceError("invalid_references")
    if len(set(ids)) != len(ids):
        raise EvidenceError("duplicate_reference")
    dh = _report_hash(debate)
    sh = _report_hash(dossier)
    if debate.get("e11_report_sha256") != sh:
        raise EvidenceError("dossier_mismatch")
    cards_data = dossier.get("cards")
    sources = dossier.get("sources")
    if type(cards_data) is not list or type(sources) is not dict:
        raise EvidenceError("invalid_evidence_schema")
    if any(type(c) is not dict or type(c.get("candidate_id")) is not str
           for c in cards_data):
        raise EvidenceError("invalid_card")
    cards = {c["candidate_id"]: c for c in cards_data}
    if len(cards) != len(cards_data):
        raise EvidenceError("duplicate_catalog_card")
    events, works = set(), set()
    for cid in ids:
        card = cards.get(cid)
        if card is None:
            raise EvidenceError("unknown_card")
        role = card.get("source")
        src = sources.get(role)
        if type(src) is not dict:
            raise EvidenceError("unknown_source")
        event = src.get("source_event_id")
        arxiv = src.get("arxiv_id")
        if type(event) not in (str, int) or not str(event):
            raise EvidenceError("missing_source_event")
        if type(arxiv) is not str or not re.fullmatch(r"\d{4}\.\d{4,5}v\d+", arxiv):
            raise EvidenceError("invalid_arxiv_id")
        events.add(str(event))
        works.add(re.sub(r"v\d+$", "", arxiv))
    return {
        "domain": "klone-evidence-receipt-subject-v1",
        "action": "draft_unverified",
        "classification": "public",
        "room_id": "public-room",
        "proposal_id": proposal_id,
        "target_version": target_version,
        "draft_sha256": hashlib.sha256(draft_text.encode("utf-8")).hexdigest(),
        "debate_sha256": dh,
        "dossier_sha256": sh,
        "card_ids": sorted(ids),
        "distinct_origin_events": len(events),
        "distinct_arxiv_works": len(works),
        "independent_sources_verified": False,
        "scientific_claim_verified": False,
    }


def sign(subject, *, secret, issued_at, ttl=300):
    """Only a trusted evidence service may invoke this with its protected key."""
    if type(secret) is not bytes or len(secret) < 32:
        raise EvidenceError("invalid_signing_key")
    if type(issued_at) is not int or type(ttl) is not int or not 1 <= ttl <= 300:
        raise EvidenceError("invalid_expiry")
    _check_subject_scope(subject)
    body = {"domain": "klone-evidence-receipt-v1", "subject": subject,
            "issued_at": issued_at, "expires_at": issued_at + ttl}
    signature = hmac.new(secret, canonical(body), hashlib.sha256).hexdigest()
    return {"body": body, "signature": signature}


def verify(receipt, expected_subject, *, secret, now):
    """Fail closed; subject must be recomputed from currently checked inputs."""
    if type(secret) is not bytes or len(secret) < 32 or type(now) is not int:
        raise EvidenceError("invalid_verification_context")
    if type(receipt) is not dict or set(receipt) != {"body", "signature"}:
        raise EvidenceError("invalid_receipt")
    body, signature = receipt["body"], receipt["signature"]
    if type(body) is not dict or set(body) != {"domain", "subject", "issued_at", "expires_at"}:
        raise EvidenceError("invalid_receipt_body")
    if type(signature) is not str or not re.fullmatch(r"[0-9a-f]{64}", signature):
        raise EvidenceError("invalid_signature")
    expected = hmac.new(secret, canonical(body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise EvidenceError("invalid_signature")
    i, e = body["issued_at"], body["expires_at"]
    if (body["domain"] != "klone-evidence-receipt-v1"
            or type(i) is not int or type(e) is not int
            or not i <= now < e or not 1 <= e-i <= 300):
        raise EvidenceError("expired_or_invalid_receipt")
    if body["subject"] != expected_subject or type(expected_subject) is not dict:
        raise EvidenceError("subject_mismatch")
    _check_subject_scope(expected_subject)
    return True
