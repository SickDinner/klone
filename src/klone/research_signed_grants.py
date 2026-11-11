"""Narrow, short-lived signed research grants for a trusted service.

This primitive authenticates an HMAC issued by a key holder, not a user.
Issuer must authenticate the principal, enforce current Hypervisor policy,
protect its key and maintain revocation/nonce state externally.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json


@dataclass(frozen=True)
class SignedResearchGrant:
    principal: str
    room_id: str
    action: str
    resource_id: str
    report_version: int
    policy_version: int
    expires_at: int
    nonce: str
    signature: str


def _payload(grant: SignedResearchGrant) -> bytes:
    return json.dumps([
        "klone-research-grant-v1", grant.principal, grant.room_id,
        grant.action, grant.resource_id, grant.report_version,
        grant.policy_version, grant.expires_at, grant.nonce,
    ], ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _key(key: bytes) -> None:
    if type(key) is not bytes or len(key) < 32:
        raise ValueError("At least 32 secret key bytes required")


def issue_research_grant(
    *, principal: str, resource_id: str, report_version: int,
    policy_version: int, expires_at: int, nonce: str, key: bytes,
) -> SignedResearchGrant:
    """Trusted issuer only; no HTTP/request-derived claims."""
    _key(key)
    if (not isinstance(principal, str) or not 1 <= len(principal) <= 128
        or not principal.strip() or not isinstance(resource_id, str)
        or not 1 <= len(resource_id) <= 128 or not resource_id.strip()
        or type(report_version) is not int or report_version < 1
        or type(policy_version) is not int or policy_version < 1
        or type(expires_at) is not int or expires_at < 1
        or not isinstance(nonce, str) or not 16 <= len(nonce) <= 128
        or not nonce.isascii()):
        raise ValueError("Invalid grant scope")
    unsigned = SignedResearchGrant(
        principal, "public-room", "research.claim.commit", resource_id,
        report_version, policy_version, expires_at, nonce, "")
    return SignedResearchGrant(
        principal, unsigned.room_id, unsigned.action, resource_id,
        report_version, policy_version, expires_at, nonce,
        hmac.new(key, _payload(unsigned), hashlib.sha256).hexdigest())


def verify_research_grant(
    *, grant: SignedResearchGrant, principal: str, resource_id: str,
    report_version: int, policy_version: int, now: int, key: bytes,
) -> bool:
    """Fail closed; caller supplies trusted clock and current policy version.

    Does NOT enforce one-time nonce use or revoked sessions. A privileged
    service must check these independently at commit time.
    """
    _key(key)
    if (not isinstance(grant, SignedResearchGrant)
        or type(now) is not int or now < 0
        or type(report_version) is not int
        or type(policy_version) is not int
        or type(grant.expires_at) is not int
        or type(grant.report_version) is not int
        or type(grant.policy_version) is not int
        or not isinstance(grant.signature, str)
        or len(grant.signature) != 64
        or not isinstance(grant.nonce, str)
        or not isinstance(grant.principal, str)
        or not isinstance(grant.resource_id, str)
        or not isinstance(grant.room_id, str)
        or not isinstance(grant.action, str)):
        return False
    if (grant.principal != principal or grant.resource_id != resource_id
        or grant.room_id != "public-room"
        or grant.action != "research.claim.commit"
        or grant.report_version != report_version
        or grant.policy_version != policy_version
        or now >= grant.expires_at):
        return False
    expected = hmac.new(key, _payload(grant), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, grant.signature)
