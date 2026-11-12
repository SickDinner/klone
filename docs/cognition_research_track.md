# KLONE Cognition Research Track (experimental)

## Scope
This is an experimental research program, **not** a claim of artificial consciousness. No generally accepted behavioral or software test establishes subjective experience. The browser lab is a deterministic toy state machine, not a neural model.

## Layers
1. Observations: explicitly scoped inputs, with source and timestamp.
2. Episodic memory: room-scoped events, correction state, provenance, retention.
3. Global workspace: limited-capacity selection of information for downstream tasks.
4. Self-model: inspectable capabilities, uncertainties, goals, and limitations.
5. Metacognition: predictions of task success and calibration against outcomes.
6. Governance: existing hypervisor, access, classification, audit and output guards.

## Experiments
- **Ablation**: compare task performance with and without workspace, memory, or self-model.
- **Calibration**: compare predicted confidence with measured correctness.
- **Continuity**: test state reconstruction across restarts without granting extra rights.
- **Causal interventions**: change one state variable and measure effects on behavior.
- **Adversarial prompts**: verify that claimed identity, emotions, or consciousness never override permissions.

## Metrics
Task success, calibration error, information retention, trace reproducibility, latency, and access-control violations. None of these measures subjective experience.

## Safety
No self-modifying permissions, covert persistence, external side effects, or claims that simulation is sentient. No ingest or write endpoints are called by the Web OS page. Experiments should be reviewable, reproducible and reversible.

## UI
Open `/static/web_os_10.html` after deployment. This UI only reads existing API endpoints. Cognition simulation and exported logs run locally in the browser.
