# Human review guide

This guide prepares substantive reviews; it records no completed review or score.
Three qualifying human reviews remain pending in the [register](peer-reviews.md).
Agent reviews and automated checks are separate evidence. Confirm reviewer
eligibility under the course rules; the lanes below are suggested scopes.

Start with the [English requirements](../requirements/cognitive-traffic-mvp-v1.md),
[task tracker](../tasks/tracker.md), [agent execution record](../tasks/agent-execution.md)
and [validation ledger](../evidence/rubric-validation.md). Record the revision
reviewed. Local tracker/specification/agent records become public evidence only
after authorized publication; an issue template or local commit proves no publication.

| Suggested lane | Inspect | Verify and report |
|---|---|---|
| Requirements, provenance and application | F01–F02, D01–D03/D06–D08; contracts, registry, sink, PostgreSQL, API and Live Map | Exactly 12 configured points; explicit missing values; source/time identity; fixture raw→Kafka→normalizer→database→API→browser; duplicate/old/replay isolation and restart persistence |
| Tests, CI and notebook boundary | Test commands, `.github/workflows/ci-light.yml`, N01–N05, notebook and artifact-review DAG | Real PostgreSQL tests actually execute; frontend checks pass; CI run belongs to reviewed revision if available; shared notebook helpers and fail-closed artifact checks; no training/model-quality claim from syntax or fixture tests |
| Telemetry, alert and bounded recovery | D09, telemetry configuration, journey probe, [runbook](../operations/api-unavailable.md), receiver/executor | Stored matching trace/log/exemplar IDs and redaction; telemetry restart retention; actual firing→webhook→diagnosis→one permitted recovery→verified journey→resolved record |

Use the existing environment or follow [README setup](../../README.md). Read the
Makefile first. For Python commands the default is the `traffic` Conda environment;
an installed alternative can be selected with `PYTHON=/absolute/path/to/python`.
Browser checks require the README's Node/Playwright prerequisites.

```bash
git rev-parse HEAD
make lint
make test
make smoke
```

For the operations lane, `make oncall-demo` includes the isolated smoke journey
and controlled recovery, so it can replace a separate `make smoke` run. These
commands create disposable assessment resources and must preserve existing stacks
and data. Do not manually fault the normal application. Smoke reports appear under
`.local/validation/`; retain exact output paths, run IDs and exit status.

`make test` starts and removes a disposable PostgreSQL container when no
`TRAFFIC_TEST_DSN` is supplied; Docker must be running. An explicit DSN must point
to a disposable test database. Direct pytest runs can skip database cases without
that DSN; report skipped cases rather than full database coverage. Do not reuse
the expired transient port in the ledger.
Frontend verification uses `npm ci --prefix frontend`, followed by
`cd frontend && npm run build && npx tsc --noEmit`. Record actual results rather
than copying historical counts. Source inspection of CI does not prove a remote run.

Expected smoke observations are 12 anchors with honest missing state before the
labelled fixture; persisted fixture data visible through the UI; preserved latest
state across duplicate/older/replay inputs and database restart. The operations
report should additionally identify the retrieved correlated trace, delivered
firing/resolved alert, incident and verified executor result. Check actual report
fields and failures. Fixtures prove integration, not live provider coverage.

Record a review using this compact format, then link it from the register:

```text
Human reviewer identity / date / reviewed revision:
Scope and requirement IDs:
Checks actually performed / commands / exit status / artifact references:
Finding: severity, file:line, reproduction, expected versus observed behavior:
Author response / change reference / verification of resolution:
Unverified acceptance and external gates:
Actual course/public review reference (or assessor-accessible private reference):
```

An honest review may find remaining work. Congestion review/alerts, evaluated
forecasts/context, departure/routes, live rights/coverage and model quality retain
their tracker status; infrastructure acceptance does not complete those features.
Hosting is deferred. No review request, issue creation or publication is performed
by preparing this guide.
