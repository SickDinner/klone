# KLONE v2.9 — Proof-Carrying Cognition (LAB; draft)

## Scope and architecture

A small **read-only composition layer** ties existing modules together rather
than recreating a parallel trust system:

1. `evidence_lineage_v26.analyze_lineage`: canonical declared input fingerprint,
   dependency/correction graph, claimant review statuses, quarantine conditions.
2. `evidence_counterfactual_v27.simulate_source_withdrawals`: declared-group
   withdrawal, descendant removal, supersession-history safety, coverage.
3. `council72_portfolio_v26.plan_council72_review`: finite 9 × 8 human-review
   proposal queue, total/per-ring **estimated** token budgets.
4. `cognition_metabolism_v28.reconcile_council_metabolism`: check **unverified**
   provider token reports against the same recomputed exact plan hash,
   check missing/failed receipts and process-wide CPU/RSS snapshots.
5. `hypervisor_runtime.HypervisorRuntime.plan`: current **policy preview** for
   `propose` in the public room, not an execution capability or identity proof.
6. `proof_carrying_cognition_v29.build_review_proof`: a deterministic JSON
   dossier with hashes, explicit hold reasons, and no raw content or source
   group labels; `verify_review_proof` replays all parts from the same inputs.

### Fail-closed behavior

- **PUBLIC-ONLY first iteration**. Any input node, requested room or
  classification outside `public-room` + `public` is rejected **before report
  generation**, because even source IDs and claim keys may be sensitive.
  Restricted/bio/sealed/debug reviews require a separately governed route.
- A report with a valid local hash is **not signed** and its sources may all be
  fabricated. An independently trusted digest may be supplied to the replay
  verifier, but this module does not prove that digest's origin.
- The current role and trace ID are untrusted caller claims. Routing is
  recomputed, but `allowed` is only a *read-only policy preview* for `propose`;
  **it never permits executing**, publishing, transferring memory, or granting
  access to another room. No approval/activation interface exists.
- Missing provider token reports, missing or failed receipts, task budget
  overruns, contested evidence, insufficient independent *declared* groups,
  incomplete source withdrawal coverage, fragility and unqueued tasks generate
  explicit `review_holds` and `hold_for_manual_review`.
- Even a hold-free output is named
  `unverified_packet_ready_for_manual_review`, **not authorization**.
- Aggregated CPU is the *Python process* measurement where available,
  not an agent-isolated CPU/energy or task-authenticity attestation.
- Inputs are bounded (512 nodes, 72 tasks, 72 receipts). Both report and
  verifier have size bounds; strict component validators reject malformed
  data, cycles and duplicate IDs.

## Example (from within a KLONE checkout)

```python
from klone.evidence_lineage_v26 import EvidenceLineageNode
from klone.council72_portfolio_v26 import ReviewCandidate
from klone.proof_carrying_cognition_v29 import ReviewProofRequest, build_review_proof

nodes = [EvidenceLineageNode(
    node_id=f"e{i}", claim_key="topic", domain="research",
    source_group=f"group{i}", content_sha256=f"{i:064x}",
    stance="supports", room_id="public-room", classification="public"
) for i in (1, 2, 3)]
task = ReviewCandidate(task_id="review1", claim_key="topic", domain="research",
                       ring=6, seat=1, priority=90, estimated_tokens=100)
request = ReviewProofRequest(task_id="review1", claim_key="topic",
                             room_id="public-room", classification_level="public",
                             actor_role="evaluator", trace_id="example1")
report = build_review_proof(nodes, [task], [], request)
assert not report["approval_granted"]
assert "telemetry_needs_review" in report["review_holds"]
```

The empty receipts list above is deliberate: an unexecuted planning request
must not be misrepresented as measured workload or completed review.

## Local testing and platform evidence

Locally, with the exact checked-out v2.6–v2.8 source modules and **a clearly
labelled stand-in hypervisor policy only for tests**, 183 focused/ancestor
cases completed: **179 passed, 4 skipped**. Of the 42 new tests, 41 passed
and one real Council72 integration case was skipped locally (requires the full
repository). The GitHub CI run is the authoritative integration of the *real*
`HypervisorRuntime` and original Council72 session code. The stand-in is
never committed, packaged, nor installed into KLONE.

The Android full suite is a separate verification task. For the new exact
commit the expected total is **1336 + 42 = 1378**; skipped-case counts may
vary by platform. Report actual results, not estimates.

## Next stages (proposal, not shipped)

| Component | Follow-on | Acceptance evidence |
|---|---|---|
| Council72 | Joint source fragility & expected information gain of new evidence | Held-out calibration + citation-cluster provenance, not raw vote counts |
| Memory Core | Corrections + temporal snapshots bound to source IDs | No rollback resurrects a corrected assertion |
| Hypervisor | Separate UID/OS principal and protected, out-of-process approval gateway | Actual peer-UID test between two isolated processes + negative cross-room tests |
| v2.5 audit | Publish checkpoint to distinct rollback-resistant trust domain | Tail deletion, replay and old-anchor rollback fail tests on real backend |
| Cognition | Provider token receipts, CPU/RSS budgets, energy and thermal probes | Source-labelled metrics; unknown stays unknown, validated Android probe |
| Genomics | Only analysis metadata can leave restricted-bio sandbox with real granted capability | No raw genomic identifiers escape in logs or report |
| Media | Asset lineage, deduplication and permitted export policies | Metadata stripping and cross-room confidentiality tests |
| Simulation | Fork/replay immutable world states without claiming real observations | Deterministic replay and synthetic-tag propagation |
| Mission Control | Proof-check viewer, holds, failures, diff across pinned commits | No report gets "verified" badge without independent source anchor |
| Local Android | Detect temperature and memory pressure with guarded work dispatch | Measure actual CPU, power, latency; task cancellation after policy revocation |

**Research design note:** Rather than targeting 72 independent large model
processes on a phone, multiplex 9 review rings with shared model contexts,
quality-aware scheduling, caching whose keys include trust scope and source
version, and a bounded inference budget. This is an optimization hypothesis
until benchmarked on actual hardware and threat-model tested.
