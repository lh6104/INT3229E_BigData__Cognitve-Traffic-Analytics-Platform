# Local rubric validation — 2026-10-27

Latest reassessment and additional execution: [rubric recheck](rubric-recheck-2026-10-27.md). Historical counts and results below remain specific to the original run.

Scope: approved readiness work on `test`, based on `43ac84e`. Execution was recorded before the user-authorized local readiness commit.
Hosting remains deferred. This record reports executed local acceptance, not an
assessment award, a public deployment, a live-data claim or human peer reviews.
The [machine report](local-smoke-2026-10-27.json) retains actual trace/incident IDs
and observed executor results with local paths, tokens and environment removed.

## Executed checks

All commands below exited **0** unless explicitly qualified. Python is 3.11;
Node is 22.23.2. Tests used a newly created environment installed with
`pip install -c constraints/python311.txt -e '.[dev]'`, followed by `pip check`.

| Check | Exact command / setup | Observed result |
|---|---|---|
| Dependency consistency | `.local/validation/python311/bin/python -m pip check` | No broken requirements |
| Unit, API and database integration, Node adapter | `TRAFFIC_TEST_DSN=postgresql://postgres:postgres@localhost:50797/traffic_analytics make test PYTHON=.local/validation/python311/bin/python` | **118 Python tests passed**, including 13 real PostgreSQL cases; **3 Node tests passed**, no skipped tests |
| Lint and compilation | `make lint PYTHON=.local/validation/python311/bin/python` | Ruff and compileall passed for source, tests, orchestration and scripts |
| Frontend types | `cd frontend && npx tsc --noEmit` | Passed |
| Frontend production build | `cd frontend && npm run build` | Client and SSR builds passed |
| Frontend dependency audit | `npm --prefix frontend audit --json` | **0 vulnerabilities**, including development dependencies; previous snapshot had 13 |
| Compose configuration | `docker compose config --quiet` | Passed |
| Alert rule behavior | `docker run --rm --entrypoint /bin/promtool -v "$PWD:/work:ro" -w /work/tests/observability prom/prometheus:v3.13.1 test rules alerts.test.yml` | SUCCESS; sustained failure fires and recovery clears the alert |
| Full real-service acceptance | `make oncall-demo PYTHON=.local/validation/python311/bin/python` | **Passed** in fresh isolated project `cognitive-rubric-98b89c18cd`; details below |
| Minimum framework compatibility | Fresh Python 3.11 env: `pip install -e '.[api]' fastapi==0.112.0 httpx==0.28.1 httpx2==2.13.0`; context-managed TestClient against actual app with repository override; `pip check` | FastAPI 0.112.0 / Starlette 0.37.2 transport and real-app health smoke passed; not the full minimum-version test matrix |
| Review and whitespace | Independent source reviews; `git diff --check` | Concrete findings fixed; final scoped re-review accepted publication retry correction |

The test DSN above was a disposable loopback-only database with demo credentials; that test stack has been removed. Do not reuse its transient port as a normal application configuration.

The primary constraints resolve FastAPI 0.141.1, Starlette 1.10.0, HTTPX 0.28.1,
HTTPX2 2.16.0 and OTEL SDK/exporter 1.29.0. Keeping both TestClient transports
supports the old/new Starlette branches without changing the supported framework
range or upgrading MLflow. Constraints intentionally pin the resolved environment;
they are not a cross-platform artifact-hash lock or a promise to test every version.

## What the combined smoke actually proved

1. One Compose startup built the repository Docker definitions and started frontend,
   API, database, Kafka, normalizer, serving sink, object storage/bootstrap and local
   observability. Fresh names, volumes and loopback ports isolated the application
   from ADG_PRO and existing traffic data. No temporary Compose override, unavailable
   registry image or manual bucket creation was used.
2. Empty storage returned all 12 configured anchors, six in each city, all missing
   with null geometry and no invented observations. A labelled `acceptance-fixture`
   was sent through **raw Kafka → normalizer → canonical sink → PostgreSQL → API →
   frontend**. Duplicate/older events preserved one latest value, history contained
   exactly two accepted observations, and replay could not replace current state.
3. PostgreSQL restart retained the persisted value. Playwright Chromium rendered
   **12 map anchors**, verified the same-origin API's labelled fixture, confirmed
   no supplied road geometry and reported no uncaught page errors.
4. Actual trace `d7c400a80c31475ba1cb4b46f04b9987` was retrieved from Tempo;
   sanitized Loki logs and Prometheus exemplars carried that **same trace ID**.
   A sentinel request query secret was absent from correlated exported logs.
   Restarting the telemetry backend retained retrievable trace and log data.
5. A restricted host executor was already listening before the isolated API was
   stopped. The semantic operator probe failed, Prometheus fired after the sustained
   threshold, Alertmanager delivered an authenticated webhook, and the runbook
   agent persisted its diagnosis and signed recovery request. The executor performed
   **one API restart**, verified the actual operator journey, and Alertmanager's
   resolved delivery produced a persisted `resolved` / `journey_pass` incident.
   Incident: `8af559764caa15690bb5d5c9895721c9946909d883112d7b3e5d629bb7f1183d`.
6. The command cleaned up only that generated test project's containers and named
   volumes. Ignored local state retains the incident database, signed queue and
   executor result for inspection. The existing ADG_PRO services were not stopped
   or recreated by the acceptance tests.

Raw local evidence is under `.local/validation/`: `final-oncall-demo.log`,
`cognitive-rubric-98b89c18cd.json`, `make-test.log`, `frontend-build.log`,
`min-api-smoke.log`, `python-install.log`, `lint.log`, and supplementary diagnostic
runs. These ignored files are not public evidence. CI is configured to upload
redacted smoke JSON/failure logs when the changed workflow is published and run.
The committed JSON summary above contains the relevant successful local results.

## Review corrections and operational boundaries

Review/test cycles corrected registry validation before DDL, reads leaking disabled
or ineligible roads, replay retaining operational mode, the wrong journey endpoint,
Uvicorn exception/query credential leakage, recovery authorization before queue
publication, lost publication retries, stale recovery requests, inaccurate resolution
state, metric exemplar mis-correlation, a frontend root-path 404, and Kafka readiness
when host ports differ. Tests include actual Uvicorn log redaction, committed
incident authorization, HMAC/claim deduplication, publication retry, authorization
expiry, rollback and concurrent duplicate PostgreSQL deliveries.

The on-call component is a **deterministic bounded runbook agent**, not an LLM. It
supports one fault/action in explicitly named isolated assessment projects. The
webhook container has no Docker socket or shell execution capability. An explicitly
started host executor alone has fixed API-restart permission; it refuses general
application/ADG project names. The persistent SQLite incident ledger is independent
of the traffic PostgreSQL dependency. This is a demonstrated local recovery flow,
not a hosted production on-call deployment.

## Conservative rubric mapping

| Criterion | Maximum | Current local/source evidence | Remaining gate |
|---|---:|---:|---|
| Problem description | 2 | 2 | None for this criterion |
| Product specification | 2 | 1 | Publish the versioned task tracker and agent evidence; no issue creation/publication is claimed |
| Agent team specification | 2 | 2 | Project roles, ownership and handoffs documented; actual agent work recorded separately |
| Context management | 2 | 2 | Root AGENTS.md references modular context/team/process documentation |
| Application | 2 | 2 | Isolated persisted event→API→browser demonstrated; broader product roadmap remains separate |
| Testing | 2 | 2 | One command passes unit, API integration, real database and Node tests |
| Containerization | 2 | 2 | Whole declared local stack starts through Compose, including frontend/database and idempotent bootstrap |
| Deployment | 2 | 0 | Deferred by user |
| CI/CD | 3 | 1 | PR/push tests configured; new PostgreSQL/Compose/browser/alert workflow has **not run on GitHub yet**; deployment stages deferred |
| Observability | 2 | 2 | Stored/viewable correlated traces, structured logs and metric exemplars; retention and redaction checked |
| User-impact alert | 1 | 1 | Actual firing and resolved webhook delivery demonstrated |
| On-call agent | 2 | 2 | Alert-triggered deterministic runbook recovery demonstrated; assessor interpretation of “agent” remains external |
| Total | **24** | **19** | **20/24 conditional post-publication target; 4 deployment-dependent points deferred** |

The CI point is source/configuration evidence, not proof that this changed
workflow has passed remotely. The last previously verified remote workflow belonged
to `43ac84e`; it does not validate these new changes. Do not report 24/24 or course
completion from this local record.

## External and data-dependent requirements

- **Three qualifying human peer reviews:** zero are evidenced in the
  [review register](../reviews/peer-reviews.md). Agent reviews are not substitutes.
- Publication of the integration branch/task tracker and a successful new PR-triggered
  GitHub Actions run require maintainer publication. The subsequent handoff authorizes a local commit only; no push or external
  messages are authorized; old `main` must not be assumed current.
- Live provider rights, 12-point coverage/direction mapping and lawful acquired
  datasets remain unverified. Fixtures are test data and are never installed in the
  normal application's storage by startup.
- No model training, final model-quality evaluation or promotion was executed.
  Notebook/DAG tests prove interface and fail-closed review behavior only. Product
  congestion alerts/reviews, evaluated source fusion, forecasts and departure/route
  support retain the [tracker's](../tasks/tracker.md) planned/data-gated status.
  Missing provider confidence and closure-specific semantics still need the later
  quality work; this infrastructure delivery is not full product P2 acceptance.
- Public hosting/dev deployment/manual production deployment are deferred. Future
  clean-machine registry/network availability and course rubric interpretation
  require external verification; this record demonstrates the tested local machine.

## Local commit preflight — 2026-10-27

The user authorized a local commit and explicitly prohibited pushing. A new
throwaway PostgreSQL container supplied isolated schemas for the fresh `make test`
run: **118 Python + 3 Node tests passed**; it was then removed. Lint, compilation,
`pip check`, Compose validation and staged whitespace checks passed again.

After route generation, the frontend type checker exposed two compatibility
issues: the router's error value is `unknown`, and the root redirect must provide
the required city search parameter. The handler annotation and redirect were
corrected. A fresh production build followed by `npx tsc --noEmit` passed; the
built SSR handler returned `/live-map?city=all` from `/` and served the destination
with HTTP 200. The npm audit still reported zero vulnerabilities. This preflight
rechecked unit/integration/types/build/SSR behavior; the full Compose/browser/
recovery evidence remains the earlier combined smoke run recorded above.
