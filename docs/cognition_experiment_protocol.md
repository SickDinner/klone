# Cognition Core 1.2: experiment protocol

## Research question
Does a bounded functional architecture improve calibrated predictions and task outcomes compared with controlled ablations? This does **not** test whether an AI has subjective experience.

## Existing experimental components
- Deterministic, bounded internal state and replay: `cognition_core.py`
- Room-permission checked read-only *aggregate* memory probe: `cognition_memory.py`
- Calibration metrics (Brier score, bins): `cognition_metrics.py`
- Pure bounded planner with abstention: `cognition_planner.py`
- API endpoints: `/api/cognition/capabilities`, `/simulate`, `/ablations`, `/memory-probe`, `/plan`

## Experiment matrix
| Condition | Workspace | Memory | Self-model | Planning |
| --- | --- | --- | --- | --- |
| Baseline | off | off | off | off |
| Memory | off | on | off | off |
| Workspace | on | off | off | off |
| Self-model | off | off | on | off |
| Combined | on | on | on | on |

Hold input signals, random seeds, budgets, scoring and permissions constant across conditions. Run 100+ independent seeded scenarios before making comparative claims. Report failures and uncertainty intervals. Do not use the presence of self-descriptive text as a consciousness metric.

## Operational safeguards
1. Experimental API is stateless and capped; no persistent cognition DB schema.
2. Planner returns a plan but cannot invoke tools.
3. Memory probe requires existing room-read permission and returns counts, not evidence text.
4. No new grants, permissions, agents, network calls or write paths.
5. Existing repository audit/security tests must pass before merging.
6. Run Python unit tests and full pytest suite in a clean checkout; browser/Termux integration still requires validation.

## Known limitations
- Toy signal dynamics and fixed action model do not establish general intelligence.
- Memory probe aggregates only a bounded sample and is not a memory-to-agent pipeline.
- No calibrated learning loop yet; Brier metrics require real labeled predictions.
- Web UI still needs production usability and accessibility testing.
