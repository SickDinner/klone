"""Offline Ed25519 evidence attestations with explicit trust roots.

Requires the optional cryptography package. Signing proves possession of a
private key, not that a test ran, a device is genuine, or deployment is safe.
No private keys are generated or persisted by this module.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

SHA = re.compile(r"^[0-9a-f]{40}$")
HEX = re.compile(r"^[0-9a-f]{64}$")


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _crypto():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise RuntimeError("Install optional dependency: pip install cryptography") from exc
    return InvalidSignature, Ed25519PublicKey


def _timestamp(value: str) -> None:
    if not isinstance(value, str):
        raise ValueError("timestamp missing")
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("timestamp needs timezone")


def validate_packet(packet: dict) -> str:
    if not isinstance(packet, dict) or packet.get("schema_version") != 1:
        raise ValueError("invalid packet schema")
    if packet.get("kind") != "klone-evidence-packet":
        raise ValueError("invalid packet kind")
    commit = packet.get("commit")
    if not isinstance(commit, str) or not SHA.fullmatch(commit):
        raise ValueError("invalid commit")
    digest = packet.get("packet_sha256")
    if not isinstance(digest, str) or not HEX.fullmatch(digest):
        raise ValueError("invalid digest")
    actual = hashlib.sha256(canonical({k: v for k, v in packet.items()
                                       if k != "packet_sha256"})).hexdigest()
    if digest != actual:
        raise ValueError("packet digest mismatch")
    if packet.get("device_identity_verified") is not False or packet.get("deployment_approval") is not False:
        raise ValueError("unsupported approval claims")
    _timestamp(packet["observed_at"])
    return digest


def message(packet: dict, witness_id: str) -> bytes:
    digest = validate_packet(packet)
    if not isinstance(witness_id, str) or not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,100}", witness_id):
        raise ValueError("invalid witness ID")
    return canonical({"domain": "KLONE-EVIDENCE-ATTESTATION-V1",
                      "witness_id": witness_id, "packet_sha256": digest,
                      "commit": packet["commit"]})


def verify(packet: dict, attestation: dict, trusted_keys: dict[str, str]) -> dict:
    result = {"signature_valid": False, "trusted_witness": False,
              "origin_authenticated": False, "deployment_approval": False,
              "reason": "unverified"}
    try:
        if not isinstance(attestation, dict) or attestation.get("schema_version") != 1:
            raise ValueError("invalid attestation")
        if attestation.get("algorithm") != "Ed25519":
            raise ValueError("unsupported signature algorithm")
        witness = attestation["witness_id"]
        msg = message(packet, witness)
        if attestation.get("packet_sha256") != packet["packet_sha256"]:
            raise ValueError("packet reference mismatch")
        key_hex = trusted_keys.get(witness)
        if not isinstance(key_hex, str):
            result["reason"] = "untrusted_witness"
            return result
        if not re.fullmatch(r"[0-9a-f]{64}", key_hex):
            raise ValueError("invalid trusted public key")
        signature = base64.b64decode(attestation["signature_b64"], validate=True)
        if len(signature) != 64:
            raise ValueError("invalid signature length")
        InvalidSignature, Ed25519PublicKey = _crypto()
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_hex)).verify(signature, msg)
        except InvalidSignature:
            result["reason"] = "bad_signature"
            return result
        result.update(signature_valid=True, trusted_witness=True,
                      origin_authenticated=True, reason="valid_signature")
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        result["reason"] = type(exc).__name__
    return result


def sign(packet: dict, witness_id: str, private_key_bytes: bytes) -> dict:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise RuntimeError("Install optional dependency: pip install cryptography") from exc
    if len(private_key_bytes) != 32:
        raise ValueError("Ed25519 raw private key must be 32 bytes")
    signature = Ed25519PrivateKey.from_private_bytes(private_key_bytes).sign(
        message(packet, witness_id))
    return {"schema_version": 1, "algorithm": "Ed25519",
            "witness_id": witness_id, "packet_sha256": packet["packet_sha256"],
            "signature_b64": base64.b64encode(signature).decode("ascii")}


def _load(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 131072:
        raise ValueError("missing or oversized JSON")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("JSON object expected")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--attestation", required=True, type=Path)
    parser.add_argument("--trusted-keys", required=True, type=Path,
                        help="JSON map of witness IDs to hex Ed25519 public keys")
    args = parser.parse_args(argv)
    result = verify(_load(args.packet), _load(args.attestation), _load(args.trusted_keys))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["signature_valid"] and result["trusted_witness"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
