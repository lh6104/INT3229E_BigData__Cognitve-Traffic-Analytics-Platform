# Cognitive Traffic agent instructions

Start with [context](docs/agents/context.md), then [team ownership](docs/agents/team.md) and [delivery process](docs/agents/process.md). These documents are modular project instructions, not evidence that a role or review has occurred.

The user-approved scope is exactly 12 monitoring points, operator monitoring first, departure/route comparison second, and Data Engineering as the core. Hosting is deferred. Read the [English specification and acceptance criteria](docs/requirements/cognitive-traffic-mvp-v1.md) and [task tracker](docs/tasks/tracker.md) before making changes. Preserve unrelated work and existing service data. Do not publish, send external messages, or fabricate measurements/reviews.

Train/evaluate/select candidate models only through `notebooks/`, importing shared `cognitive_traffic` helpers. Airflow prepares data, checks quality and validates notebook-produced artifacts. A passing unit test is not evidence of live provider coverage, learned model quality, a human peer review, deployment, or real-service E2E.

Canonical local commands: `make up`, `make lint`, `make test`, `make smoke`, `make oncall-demo`. Read the Makefile before execution; smoke and fault demonstrations must use isolated resources. Report exact commands, exit status, artifact paths and remaining external gates. Do not claim commands passed without execution evidence.
