# Rubric Readiness Implementation Plan

**Goal:** Close locally implementable rubric gaps without deployment or invented external evidence.
**Authority:** User-approved rubric audit, followed by “solve all the problem”.
**Scope:** Work on the existing `test` branch as requested previously. Hosting remains deferred. Preserve existing data and unrelated stacks. No push, fabricated peer reviews, provider measurements, or unearned score claims.

## Work packages

- [x] Documentation: English specification, project agent roles/process/context, public tracker source, review instructions, evidence boundaries, and correct stale claims/imports. Acceptance: executable documented commands, valid local links, actual evidence recorded separately from external gates.
- [x] Serving path: transactional canonical-event sink, dataset/mode eligibility, idempotency and monotonic current state, migration/bootstrap, 12 monitoring anchors and explicit missing state in API/UI. Acceptance: unit cases plus real isolated PostgreSQL and Kafka-to-API persistence smoke, benchmark/replay isolation, restart persistence.
- [x] Operations: correlated request traces/structured logs/metrics, collection and viewer, user-journey probe/alert, bounded autonomous on-call runbook and incident evidence. Acceptance: redaction and trace propagation, rule tests, actual fault→alert→recovery→resolved run, no unrestricted Docker access in webhook service.
- [x] Integration: reproducible Compose stack with frontend and idempotent bootstrap, working images, Python constraints including both TestClient transports, targeted frontend security fixes, PR tests and Compose smoke. Acceptance: clean dependency install, pip check, unit/integration tests, frontend build/audit, fresh isolated one-command startup and persistence checks.
- [x] Review: independent whole-change review, fix substantive findings, update evidence/scorecard with verified commands and remaining external requirements.

## Coordination

Independent workers own documentation, serving, and operations; controller owns Compose, dependencies, CI and cross-component acceptance. Workers do not commit or push. Shared API/Compose interfaces are communicated before integration. Keep a ledger in this document; test results are recorded in `docs/evidence/rubric-validation.md` only after execution. Tests use an isolated Compose project and ports, never stop ADG_PRO or remove existing volumes.

## External gates

Three qualifying human peer reviews, public branch/task tracker publication, live provider rights/coverage and real data, and public hosting cannot be certified from local files. Provide concrete artifacts and instructions; report these gates honestly.


## Completion record — 2026-10-27

Local acceptance completed; see `docs/evidence/rubric-validation.md` and the redacted
machine report. The final isolated `make oncall-demo` exited 0, including browser,
restart persistence, trace/log/exemplar lookup, telemetry retention and an actual
alert-triggered API restart with verified resolution. The executor was running
before fault injection. `make test` passed 118 Python tests (including 13 real
PostgreSQL cases) plus 3 Node tests. Independent review findings were fixed and
the final queue-publication retry correction was independently re-reviewed.

Ruling: use a small persistent SQLite operational ledger independent of the traffic
PostgreSQL dependency, so an operational-store outage does not erase incident
diagnosis. No extra telemetry database is implemented; standard LGTM stores telemetry.
Ruling: the on-call implementation is an explicitly documented deterministic runbook
agent, with signed committed authorization and an isolated-project API-only executor.
It is not an LLM agent or an unrestricted production remediation service.

Public task publication, three real peer reviews, live source rights/coverage,
model evaluation and deployment remain external/data-dependent gates. These
checks close local rubric infrastructure gaps, not the entire product roadmap.
