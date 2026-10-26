# Operator journey unavailable: bounded recovery

Status: implemented local deterministic runbook; actual alert delivery and recovery must be recorded separately in the validation evidence. This agent does not use an LLM or claim general operational intelligence.

The operator journey checks HTTP success and the JSON meaning of `/system/health`, then reads `/traffic/current` and the LiveMap `/monitoring/points` endpoint. The latter must return exactly the 12 approved point identities with matching cities, valid anchor coordinates, required fields and explicit missing/stale/live status. Missing points must have null measurements. PostgreSQL must be up. A list with zero measurements is valid. Missing provider coverage or missing forecasts do not trigger an outage. Thirty seconds of failed journey probes produces `OperatorJourneyUnavailable`; a missing or stale probe creates a separate warning with no automatic recovery.

Prometheus sends firing/resolved alerts through Alertmanager to the authenticated oncall receiver. The receiver rechecks the journey, persists its diagnosis, suppresses duplicates, and creates at most one HMAC-authenticated API restart request per alert fingerprint/start time. A five minute global cooldown prevents a second incident from requesting another restart. Healthy journeys receive no action. Unsupported alerts receive no action. The receiver has neither Docker access nor a shell execution interface.

The executor runs explicitly on the developer host. It accepts only isolated project names matching `cognitive-rubric-*`, a signed request no more than ten minutes old, and action `restart_api`. Before any mutation it checks the committed incident authorization in `queue.parent/incidents.sqlite` and repeats the semantic journey. A recovered journey records `already_healthy` without restarting. Its sole Docker command is `docker compose -p PROJECT restart api`, run from this repository. A durable claim is written before execution; even a process crash cannot retry that request. It verifies both read endpoints for up to 24 seconds and records `verified` or `escalated`. Failed restart, restart timeout, failed journey verification and expired authenticated authorization persist a terminal `escalated` state and reason in the incident ledger, with no resolved timestamp. Invalid signatures cannot mutate an incident. This is a single recovery attempt, with no arbitrary shell commands or remote execution endpoint. A resolved delivery additionally rechecks the journey before marking the incident resolved. Unknown resolutions return `unknown_resolution`; failed verification records escalation with no resolved timestamp.

## Isolated acceptance procedure

Run only against the dedicated Compose project created for acceptance. Substitute the project's state directory and published API port:

```bash
python -m cognitive_traffic.operations.recovery_executor \
  --project cognitive-rubric-acceptance \
  --queue-dir /tmp/cognitive-rubric-acceptance/oncall/queue \
  --token-file /tmp/cognitive-rubric-acceptance/oncall/token \
  --api-url http://localhost:18000
```

The loop waits for authenticated requests. To process existing requests once, add `--once`. On another terminal, stop **only** the isolated project's API (`docker compose -p cognitive-rubric-acceptance stop api`). Leave Prometheus, the probe, Alertmanager, PostgreSQL and oncall running. Allow approximately 45 seconds for the sustained failure and delivery. The executor should restart the API, verify the read journey, then receive a resolved delivery. Stopping PostgreSQL is not a supported automated fix and should escalate after the single unsuccessful API recovery attempt.

Evidence resides in the persistent `incidents.sqlite` database (`incidents` table), signed `queue/*.json` requests, and `queue/*.result` executor results. Preserve these with Prometheus alert state and timestamps; do not publish the token. An unavailable executor leaves the incident at `recovery_requested`; it is not evidence of recovered service. Escalation requires human diagnosis of PostgreSQL/connectivity/configuration. The runbook intentionally cannot remediate unrelated services.
