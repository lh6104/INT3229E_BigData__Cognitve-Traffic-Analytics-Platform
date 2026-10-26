# Rubric recheck and acceptance hardening — 2026-10-27

Reviewed baseline: `7b915ba`, with user-authorized local improvements to be folded
into the same commit. No push, external review request or deployment is authorized.
This is a conservative self-assessment, not an awarded grade. The [earlier
validation](rubric-validation.md) retains the original full-stack evidence.

## Criterion-by-criterion recheck

| Criterion | Maximum | Supported local/source score | Evidence and remaining requirements |
|---|---:|---:|---|
| Problem description | 2 | 2 | [README](../../README.md) describes the operator problem, 12 anchors, behavior and limitations. The [English spec](../requirements/cognitive-traffic-mvp-v1.md) distinguishes target behavior from implementation. |
| Product specification | 2 | 1 | [Requirements/AC](../requirements/cognitive-traffic-mvp-v1.md), [task tracker](../tasks/tracker.md), [actual agent execution](../tasks/agent-execution.md). The new tracker remains local; public publication is still required for the second point. |
| Agent team specification | 2 | 2 | [Team ownership and handoffs](../agents/team.md), [delivery process](../agents/process.md), actual work recorded separately. |
| Context management | 2 | 2 | [AGENTS.md](../../AGENTS.md) links modular context, team, process, requirements and current tasks. |
| Application | 2 | 2 | [Compose](../../docker-compose.yml), [transactional sink](../../src/cognitive_traffic/streaming/serving.py), [API](../../src/cognitive_traffic/api/main.py), [map](../../frontend/src/components/live-map/LiveMapView.tsx); real event persistence and browser evidence. HCMC selections now retain their city; UI horizons are +15/+60. This is the implemented infrastructure app, not completion of F01–F10. |
| Testing | 2 | 2 | [Makefile](../../Makefile), [full-suite runner](../../scripts/run_tests.py), unit/API/real-PostgreSQL/Node tests. Plain `make test` now provisions a disposable DB if needed; it cannot silently omit the real database tests. |
| Containerization | 2 | 2 | Default Compose contains frontend, API, database, broker, workers, idempotent schema/bucket bootstrap and telemetry. A [capacity preflight](../../scripts/compose_smoke.py) protects a running repository stack from the observed undersized concurrent acceptance scenario; the earlier full-stack result remains historical evidence. |
| Deployment | 2 | 0 | Deferred by the user; no hosted or deployed-demo claim. |
| CI/CD | 3 | 1 | [PR/push workflow](../../.github/workflows/ci-light.yml) includes PostgreSQL, frontend build/types/audit and full smoke. The changed revision has not run remotely. No automated dev deployment or approved production deployment is implemented. |
| Observability | 2 | 2 | Stored/viewable correlated trace, structured logs and metric exemplars, redaction and backend-restart retention demonstrated. [Telemetry guide](../operations/observability.md). |
| User-impact alert | 1 | 1 | [Prometheus rules](../../infra/prometheus/alerts.yml), semantic API read probe and actual firing/resolved webhook evidence. This monitors API read impact, not every frontend/browser outage. |
| On-call agent | 2 | 2 | Authenticated alert → deterministic runbook diagnosis → one allowlisted isolated API restart → verified resolution. [Executor](../../src/cognitive_traffic/operations/recovery_executor.py) now persists terminal failures/expiry as escalation. Normal `make up` has no host executor; general production remediation and an LLM agent are not claimed. |
| **Total** | **24** | **19** | **Conditional post-publication target: 20/24. Four deployment-dependent points remain deferred.** |

The on-call point assumes the rubric accepts the demonstrated deterministic
runbook agent; confirm assessor interpretation rather than claiming LLM capability.

## What changed to protect these points

1. **Repeatable testing:** `make test` now starts a uniquely named, loopback-only,
   disposable PostgreSQL instance unless an explicit test DSN is provided. It runs
   both suites, propagates nonzero results, and removes only its own container and
   anonymous volume. `make test-unit` explicitly names the lighter check. Runner
   tests cover unavailable Docker, startup timeout, test failure and cleanup failure.
2. **Trustworthy failure evidence:** failed restart, timeout, failed verification
   and expired signed authorization leave the incident `escalated` with a reason
   and no resolved timestamp. Invalid signatures cannot change incident state;
   conditional writes preserve concurrent resolution and single-attempt limits.
3. **One cohesive application:** a regression first reproduced an HCMC point
   navigating to `city=hanoi` from All. The callback now passes the selected point's
   actual city. The forecast page and chart display only the approved +15/+60
   horizons; generic backend support for other horizons remains separate.
4. **Review readiness:** the [PR template](../../.github/PULL_REQUEST_TEMPLATE.md)
   and [human review guide](../reviews/reviewer-guide.md) connect requirements,
   acceptance, exact commands and real findings. They do not count as completed
   peer reviews or public publication.
5. **Capacity-aware acceptance:** an additional full stack failed Kafka readiness
   with exit 137 while the normal traffic app and ADG_PRO ran in a 3.69 GiB Docker
   VM. A smaller-memory trial also failed; that unproven tuning was removed, not
   committed as a working optimization. Only generated test stacks were removed.
   The smoke now refuses a second repository stack below 5 GiB of Docker-reported
   memory, before creating resources, with an actionable message. A 6 GiB or larger
   Docker allocation is recommended for concurrent acceptance, not guaranteed
   sufficient for arbitrary workloads. Three preflight regressions cover small
   VM/no existing stack, small VM/existing stack and larger VM/existing stack.


Machine-readable outcome summary: [recheck summary](rubric-recheck-summary-2026-10-27.json).

## Fresh execution record

- `make test PYTHON=.local/validation/python311/bin/python`: **exit 0**, **133 Python
  tests + 3 Node tests passed**, no test DSN supplied and no skipped PostgreSQL cases.
  The runner started and cleaned up its own disposable database.
- `make lint PYTHON=.local/validation/python311/bin/python`, `pip check`, base Compose validation, `git diff --check`: **exit 0**.
- `cd frontend && npm run build && npx tsc --noEmit`: **exit 0**.
  `npm audit --json`: **zero vulnerabilities**.
- Browser red/green: the new real-browser HCMC navigation test **failed** on the
  original wrong-city URL, then **2 browser tests passed** after the fix against
  isolated PostgreSQL/API/frontend. That focused run is not Kafka/telemetry E2E.
- Independent read-only re-audits covered documentation, application/testing and
  operations. The final scoped code review found no blocking issue. Review is
  separate from execution and from human course participation.

Full-stack rerun on the amended source is **not verified in this constrained
concurrent environment**: two startup attempts failed (default memory and an
abandoned lower-memory trial). The now-implemented preflight was then exercised
against the actual running environment: `make oncall-demo` exited **2**, with the
capacity explanation, before creating another test stack. The original successful
complete run remains in the earlier validation record; it must not be presented
as a new complete pass for this amendment. Raw local logs are under `.local/validation/`, including
`rubric-recheck-tests.log`, `rubric-recheck-frontend.log`,
`browser-regression-red.log`, `browser-regression-rebuild.log`,
`rubric-recheck-red.log`, `rubric-recheck-oncall.log` and
`rubric-recheck-capacity.log`.

## External gates and next score gain

Read-only GitHub verification during this recheck found remote `test` still at
`43ac84e`. Its [successful Actions run](https://github.com/lh6104/INT3229E_BigData__Cognitve-Traffic-Analytics-Platform/actions/runs/40285187547)
was a **push** run on that old revision; it validates neither `7b915ba` nor the
amended change. The current local tracker/new workflow are not public yet.

1. Maintainer publication of the branch/tracker and successful new PR-triggered
   CI can establish the remaining specification/public-task point and remote CI
   evidence. No local-only edit legitimately closes that publication gate.
2. **Three qualifying human reviews remain mandatory and zero are evidenced.**
   Follow the guide/register; agent reviews are not substitutes.
3. Hosting/deployment remains deferred. Configuration without actual delivery does
   not earn deployment/extra CI/CD points. Do not deploy merely to change the score.
4. Provider rights/coverage, true confidence/closure semantics, lawful data,
   notebook-based model evaluation, product congestion alerts/reviews, source
   fusion and departure/route support remain the separate planned/data-gated
   product roadmap. They must not be called complete because infrastructure passes.
