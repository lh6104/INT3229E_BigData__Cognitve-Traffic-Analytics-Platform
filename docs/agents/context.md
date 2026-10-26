# Project context

Instruction precedence is system/developer instructions, direct user instructions, applicable `AGENTS.md`, approved product requirements, scoped specifications, implementation plans, then historical research. Resolve conflicts using the higher authority; retain evidence of the decision.

Read only context needed for the task:

| Question | Authority |
|---|---|
| Product scope and acceptance | [MVP v1.3](../requirements/cognitive-traffic-mvp-v1.md) |
| Architecture and storage ownership | [Architecture](../architecture.md) |
| Current work and external blockers | [Task tracker](../tasks/tracker.md) |
| Delivery phases | [Roadmap](../superpowers/plans/2026-10-26-cognitive-traffic-mvp-roadmap.md) |
| Registry and eligibility | [P1 specification](../superpowers/specs/2026-10-26-registry-dataset-boundaries.md), `configs/sources.yaml`, `configs/datasets.yaml` |
| Current acceptance evidence | [Rubric validation](../evidence/rubric-validation.md) |
| Required human reviews | [Peer review register](../reviews/peer-reviews.md) |

Kafka is the event log; MinIO/S3 owns raw history and artifacts; PostgreSQL owns traffic serving state; the independent SQLite on-call ledger persists incident evidence in the mounted operations state directory; API/UI serve that state. A monitoring anchor is not a verified directed provider segment. Missing TomTom coverage is not speed zero. Weather/RSS context is not causal proof. Replay/reprocessing and benchmark events must not silently overwrite live current state.

The `test` branch is the assessment integration branch for this work. Never infer current branch, service state or test results from a historical note: inspect them. A new agent should read its tracker row, inspect scoped paths and current diff, identify required acceptance evidence, and follow the handoff format in the process document.
