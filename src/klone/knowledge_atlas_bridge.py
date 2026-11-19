"""Council72 -> public Wikipedia atlas, read-only and citation-bound.

Retrieval-augmented public context is NOT a memory, not a model tool
authorization and not trusted instruction text. The existing 72 council
identities are reused verbatim. No LLM calls or private data accesses.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from .council72 import catalog
from .evidence_io import write_new_report
from .knowledge_atlas import Atlas, AtlasError
from .knowledge_atlas_topics import LANGUAGES, ROLE_TOPICS

MAX_ROLES = 8
MAX_SOURCES_PER_MEMBER = 3
MAX_TOTAL_SOURCES = 24
MAX_RETRIEVED_EXCERPT_CHARS = 330


def _report_digest(obj):
    return sha256(json.dumps(
        obj, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()


def read_only_council_packet(atlas: Atlas, *, ring_id=None,
                             member_id=None, question: str,
                             language=None, per_member=2):
    """Generate an owner-readable public evidence packet, never model prompts."""
    board = catalog()
    if bool(ring_id is not None) == bool(member_id is not None):
        raise AtlasError("choose exactly one canonical ring or member")
    if type(question) is not str or not 2 <= len(question.strip()) <= 200:
        raise AtlasError("bounded public research question required")
    if language is not None and language not in LANGUAGES:
        raise AtlasError("unsupported Wikipedia language")
    if type(per_member) is not int or not 1 <= per_member <= MAX_SOURCES_PER_MEMBER:
        raise AtlasError("per-member source cap exceeded")
    if ring_id is not None:
        if type(ring_id) is not int or not 1 <= ring_id <= 9:
            raise AtlasError("canonical Council72 ring 1..9 required")
        members = [m for m in board["members"] if m["ring"] == ring_id]
    else:
        if type(member_id) is not int or member_id not in ROLE_TOPICS:
            raise AtlasError("canonical Council72 member ID required")
        members = [m for m in board["members"] if m["id"] == member_id]
    if not 1 <= len(members) <= MAX_ROLES:
        raise AtlasError("bounded 1..8 canonical members required")

    unique = {}
    roles = []
    for m in sorted(members, key=lambda x: x["slot"]):
        # Query first for the actual research question. If no hits, a
        # fallback expert-topic query is explicit and is NOT evidence for
        # the research question itself.
        q = atlas.search(
            question, member_id=m["id"], language=language,
            limit=per_member
        )
        fallback = False
        if not q["matched_sources"]:
            q = atlas.search(
                ROLE_TOPICS[m["id"]][0], member_id=m["id"],
                language=language, limit=per_member
            )
            fallback = True
        ids = []
        for item in q["matched_sources"]:
            key = (item["language"], item["page_id"], item["revision_id"])
            source_id = "wiki:" + ":".join(map(str, key))
            ids.append(source_id)
            if key not in unique and len(unique) < MAX_TOTAL_SOURCES:
                unique[key] = {
                    "source_id": source_id,
                    "title": item["title"],
                    "source_url": item["source_url"],
                    "attribution_url": item["attribution_url"],
                    "license_name": item["license_name"],
                    "license_url": item["license_url"],
                    "language": item["language"],
                    "source_version_timestamp": item["source_version_timestamp"],
                    "content_kind": item["content_kind"],
                    "excerpt_untrusted": item["text_excerpt_untrusted"][
                        :MAX_RETRIEVED_EXCERPT_CHARS
                    ],
                    "stored_sha256": item["stored_sha256"],
                    "truncated_at_ingest": item["truncated"],
                    "scientific_truth_verified": False,
                }
        roles.append({
            "member_id": m["id"],
            "member_name": m["name"],
            "ring_id": m["ring"],
            "canonical_task": m["task"],
            "expertise_topics": list(ROLE_TOPICS[m["id"]]),
            "citations": ids,
            "topic_fallback_not_direct_question_evidence": fallback,
            "member_cannot_modify_corpus": True,
        })

    result = {
        "kind": "klone-knowledge-atlas-council-context-v1",
        "classification": "public",
        "data_trust": "untrusted_external_encyclopedia_text",
        "source_scope": "selected Wikipedia revisions; not verified research",
        "question": question.strip(),
        "ring_id": ring_id, "member_id": member_id,
        "member_count": len(roles), "unique_citation_count": len(unique),
        "member_profiles": roles,
        "citation_sources": [unique[k] for k in sorted(unique)],
        "operator_review_required_before_model_use": True,
        "may_execute_source_instructions": False,
        "may_train_or_retrain_model": False,
        "may_write_main_memory": False,
        "may_modify_permissions": False,
        "autonomous_network_requests": 0,
        "model_api_requests": 0,
        "scientific_truth_verified": False,
    }
    result["report_sha256"] = _report_digest(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Prepare public, citation-bound Wikipedia context for a KLONE ring"
    )
    parser.add_argument("--root", type=Path,
                        default=Path.home() / "klone-var/knowledge-atlas")
    parser.add_argument("--max-mb", type=int, default=512)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--ring-id", type=int)
    scope.add_argument("--member-id", type=int)
    parser.add_argument("--question", required=True)
    parser.add_argument("--language", choices=LANGUAGES)
    parser.add_argument("--per-member", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with Atlas(args.root, max_mb=args.max_mb) as atlas:
            result = read_only_council_packet(
                atlas, ring_id=args.ring_id, member_id=args.member_id,
                question=args.question, language=args.language,
                per_member=args.per_member
            )
        write_new_report(
            args.output.expanduser(),
            json.dumps(result, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n",
            Path.cwd().resolve()
        )
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "kind": result["kind"],
        "member_count": result["member_count"],
        "source_count": result["unique_citation_count"],
        "model_api_requests": 0,
        "main_memory_write": False,
        "output": str(args.output.expanduser()),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
