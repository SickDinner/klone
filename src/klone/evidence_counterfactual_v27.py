"""Read-only source-withdrawal stress testing for KLONE evidence lineage v2.7 (LAB).

Declared source groups, dependencies and hashes are untrusted metadata.
This simulator does not execute tasks, grant privileges, read files, or change
Council72 decisions. Removing a source also removes observations *dependent*
on that source, including supersession descendants, never resurrecting history.
A source-withdrawal simulation is not an independent-source verification.
"""
from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
import json

from .evidence_lineage_v26 import EvidenceLineageNode, analyze_lineage

_MAX_GROUPS = 32


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      allow_nan=False, separators=(',', ':')).encode('ascii')


def _withdraw_closure(nodes: Sequence[EvidenceLineageNode], group: str) -> list[EvidenceLineageNode]:
    """Remove target group and all nodes transitively citing removed parents."""
    removed = {n.node_id for n in nodes if n.source_group == group}
    while True:
        derived = {n.node_id for n in nodes if n.node_id not in removed and (
            any(parent in removed for parent in n.dependencies) or
            n.supersedes in removed
        )}
        if not derived:
            break
        removed.update(derived)
    return [n for n in nodes if n.node_id not in removed]


def simulate_source_withdrawals(nodes: Sequence[EvidenceLineageNode], *,
                                minimum_candidate_clusters: int = 2,
                                max_source_groups: int = 16) -> dict:
    """Report candidate fragility under individual *declared* group withdrawals.

    Conservative v2.6 lineage is always validated first. Missing descendant
    evidence is removed as well, so the resulting graph remains self-contained.
    No group name, content hash, raw evidence or source ref is returned. A
    pseudonymous group digest is a lookup hint, NOT a privacy guarantee.
    """
    if (type(max_source_groups) is not int or
            not 1 <= max_source_groups <= _MAX_GROUPS):
        raise ValueError('invalid_withdrawal_limit')
    # Take one immutable collection snapshot; v2.6 validates cardinality,
    # cross-room safety, identities, cycles and correction chain constraints.
    source = tuple(nodes) if isinstance(nodes, Sequence) and not isinstance(nodes, (str, bytes)) else nodes
    baseline = analyze_lineage(source, minimum_candidate_clusters=minimum_candidate_clusters)
    by_claim = {c['claim_key']: c for c in baseline['claims']}
    groups = sorted({node.source_group for node in source})
    # Once corrected in the original history, an old assertion must not
    # silently become supporting evidence just because the correction source
    # is withdrawn in a counterfactual simulation.
    originally_superseded = {node.supersedes for node in source if node.supersedes is not None}
    cases = []
    counts = {claim: 0 for claim in by_claim}
    for group in groups[:max_source_groups]:
        kept = _withdraw_closure(source, group)
        changed = []
        if kept:
            outcome = analyze_lineage(kept, minimum_candidate_clusters=minimum_candidate_clusters)
            now = {row['claim_key']: row for row in outcome['claims']}
        else:
            now = {}
        still_superseded = {node.supersedes for node in kept if node.supersedes is not None}
        reactivated = originally_superseded - still_superseded
        reactivated_claims = {node.claim_key for node in kept if node.node_id in reactivated}
        for claim in sorted(by_claim):
            old_status = by_claim[claim]['review_status']
            new_status = now[claim]['review_status'] if claim in now else 'no_evidence_remaining'
            # Never promote a formerly corrected assertion to a fresh candidate.
            # Retain contested/quarantined outcomes when these are stricter.
            if claim in reactivated_claims and new_status == 'candidate_for_manual_review':
                new_status = 'unresolved_historical_supersession_requires_review'
            if old_status != new_status:
                changed.append({'claim_key': claim, 'from': old_status, 'to': new_status})
            if old_status == 'candidate_for_manual_review' and new_status != old_status:
                counts[claim] += 1
        cases.append({
            'declared_group_hint_sha256': sha256(b'klone-v27-declared-group\x00' + group.encode('utf-8')).hexdigest(),
            'removed_observation_count': len(source) - len(kept),
            'previously_superseded_assertions_reactivated': len(reactivated_claims),
            'status_changes': changed,
            'candidate_status_downgraded': any(x['from'] == 'candidate_for_manual_review' and
                                               x['to'] != x['from'] for x in changed),
        })
    tested_all = len(groups) <= max_source_groups
    claim_impact = []
    for claim in sorted(by_claim):
        claim_impact.append({
            'claim_key': claim,
            'baseline_status': by_claim[claim]['review_status'],
            'tested_group_removals_downgrading_candidate': counts[claim],
            'single_declared_group_failure_detected': counts[claim] > 0,
            'complete_one_group_withdrawal_coverage': tested_all,
            'manual_review_required': True,
        })
    result = {
        'schema_version': 1, 'kind': 'klone-evidence-counterfactual-v27-lab',
        'baseline_analysis_sha256': baseline['analysis_sha256'],
        'declared_input_sha256': baseline['declared_input_sha256'],
        'declared_group_count': len(groups),
        'withdrawals_examined': len(cases),
        'coverage_complete': tested_all,
        'cases': cases, 'claims': claim_impact,
        'source_independence_authenticated': False,
        'source_group_hints_not_anonymized': True,
        'raw_content_included': False,
        'execution_enabled': False, 'memory_write_enabled': False,
        'approval_granted': False,
        'note': 'Counterfactual declared-group sensitivity only; no trust or authorization.',
    }
    result['analysis_sha256'] = sha256(_canonical(result)).hexdigest()
    return result
