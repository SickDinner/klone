"""GitHub Issue/Termux provenance checks. Does not authenticate device identity."""
from __future__ import annotations
import json
from collections.abc import Mapping
from .termux_evidence_adapter import normalize_termux_comment

ALLOWED = frozenset({"status", "git_status", "tests", "health"})

def verify_termux_issue_comment(*, issue: Mapping, comment: Mapping,
                                repository: str, trusted_actor: str,
                                expected_action: str, expected_commit: str) -> dict:
    if not isinstance(issue, Mapping) or not isinstance(comment, Mapping):
        raise ValueError("invalid GitHub objects")
    if not repository or not trusted_actor or expected_action not in ALLOWED:
        raise ValueError("invalid trusted configuration")
    if not isinstance(expected_commit, str) or len(expected_commit) != 40 or any(
        char not in "0123456789abcdef" for char in expected_commit
    ):
        raise ValueError("full expected SHA required")
    number = issue.get("number")
    if type(number) is not int or number < 1 or "pull_request" in issue:
        raise ValueError("invalid issue")
    prefix = "https://api.github.com/repos/" + repository
    if issue.get("repository_url") != prefix:
        raise ValueError("repository mismatch")
    labels = issue.get("labels")
    if not isinstance(labels, list) or "klone-termux-task" not in {
        entry.get("name") for entry in labels if isinstance(entry, Mapping)
    }:
        raise ValueError("missing bridge label")
    author, commenter = issue.get("user"), comment.get("user")
    if not isinstance(author, Mapping) or not isinstance(commenter, Mapping):
        raise ValueError("missing GitHub actor")
    if author.get("login", "").lower() != trusted_actor.lower():
        raise ValueError("untrusted issue author")
    if commenter.get("login", "").lower() != trusted_actor.lower():
        raise ValueError("untrusted comment author")
    if comment.get("issue_url") != prefix + "/issues/" + str(number):
        raise ValueError("comment issue mismatch")
    try:
        request = json.loads(issue.get("body") or "")
    except (ValueError, TypeError):
        raise ValueError("invalid task JSON") from None
    if request != {"action": expected_action}:
        raise ValueError("task action mismatch")
    if not isinstance(comment.get("body"), str):
        raise ValueError("invalid comment")
    evidence = normalize_termux_comment(
        comment["body"], action=expected_action, issue_number=number,
        expected_commit=expected_commit, observed_at=comment.get("created_at"),
    )
    return {"evidence": evidence, "github_actor_verified": True,
            "device_identity_verified": False,
            "commit_on_device_verified": False, "deployment_approval": False}
