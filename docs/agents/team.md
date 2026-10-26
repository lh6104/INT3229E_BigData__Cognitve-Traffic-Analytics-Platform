# Agent team and ownership

These are project responsibilities and handoff contracts. Assignment and actual execution must be documented separately; naming a role does not certify an independent review.

| Role | Responsibility and owned paths | Handoff and acceptance |
|---|---|---|
| Controller / integration | `Makefile`, Compose, Docker images, dependencies, CI, cross-component configuration | Assign disjoint work; agree topics, schema, ports and env variables; collect fresh isolated-stack evidence |
| Data / serving implementer | `contracts/`, `storage/`, `streaming/serving.py`, migrations, registry-based API/UI and persistence tests | Provide contract version, eligibility/idempotency rules, migration safety, duplicate/old-event/restart evidence |
| Operations implementer | `monitoring/`, `operations/`, observability/alerts/runbooks and operations tests | Provide trace propagation/redaction, semantic user-journey probe, alert lifecycle, restricted recovery and persistent incident evidence |
| Documentation / model-boundary implementer | `AGENTS.md`, `docs/agents`, requirements/research/specs, tracker/review register, README/RESUME, training notebook and lifecycle DAG | English requirements with stable IDs; truthful evidence labels; notebook-only training and fail-closed artifact review |
| Independent reviewer | Read-only review of scoped diff and acceptance evidence; no ownership of the implementation being reviewed | Return concrete findings with file/line, severity and reproduction; controller fixes and requests verification |

The 2026-10-26 readiness implementation used controller-assigned documentation, serving and operations work packages. The audit preceding it used independent read-only specialist agents; these are agent audits, not human course peer reviews. Record future agent sessions and reviewer results in [execution evidence](../tasks/agent-execution.md), with exact scope and status. Do not retrospectively invent message transcripts, names, scores or approvals.

Humans retain product scope, source rights, publication/deployment and course peer-review decisions. Three real qualifying human reviews remain an external gate in the [review register](../reviews/peer-reviews.md).
