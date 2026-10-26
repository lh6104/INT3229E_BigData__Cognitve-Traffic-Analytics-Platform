# Cognitive Traffic

Cognitive Traffic helps a traffic operator inspect exactly 12 configured points in Hanoi and Ho Chi Minh City, distinguish missing or failed sources from real congestion, and trace measurements to their provenance. Kafka carries events, MinIO/S3 retains history/artifacts, PostgreSQL serves operational state, and FastAPI/React expose the operator journey.

The approved product also targets evidence-backed alerts, +15/+60-minute point forecasts and bounded departure/route-template comparison. Those product requirements have separate data/evaluation gates. Empty points remain visible with explicit unavailable state; no traffic measurements, road geometry, forecasts or provider coverage are invented to fill the dashboard.

Start with [requirements and acceptance criteria](docs/requirements/cognitive-traffic-mvp-v1.md), the [public task tracker source](docs/tasks/tracker.md), [current verification evidence](docs/evidence/rubric-validation.md), [architecture](docs/architecture.md), and [agent instructions](AGENTS.md). Hosting is deferred. [Human review status](docs/reviews/peer-reviews.md) requires three real qualifying reviews; automated/agent audits do not substitute.

## Run the local application

Prerequisites: Docker Engine with Docker Compose v2, enough resources for the declared stack, and available configured host ports. From the repository root:

```bash
cp .env.example .env
make up
```

`make up` builds and starts the frontend, API, database, broker, serving consumer, idempotent database/object-store bootstrap and local observability. MinIO is built from checksum-verified upstream source because the original registry images are unavailable; the first build can take several minutes. Python runtime/dev dependencies use the tested [Python 3.11 constraints](constraints/README.md), and frontend installs use `package-lock.json`. No separate `make api`, temporary Compose override or manual bucket setup is part of the canonical path. Provider polling and model inference remain explicit optional profiles; a provider key or a validated model is not required to display unobserved registry points.

| Local service | Default address |
|---|---|
| Application | <http://localhost:5173> |
| API / OpenAPI | <http://localhost:18000/docs> |
| PostgreSQL | `localhost:15433` |
| Kafka | `localhost:9092` |
| MinIO API / console | <http://localhost:19000> / <http://localhost:19001> |
| Redis | `localhost:6380` |
| MLflow, optional profile | <http://localhost:5000> |
| Grafana telemetry viewer | <http://localhost:13000> |
| Prometheus | <http://localhost:19090> |
| Alertmanager | <http://localhost:19093> |
| Restricted on-call receiver | <http://localhost:19095> |

Credentials and overrides come from `.env.example`/Compose. Use configured local demo credentials only for local operation. Inspect `docker compose config` for actual ports if overriding defaults. Stopping with `make down` retains named volumes; destructive volume removal is not a normal startup step.

## Development and verification

For host-side Python commands, use Python 3.11 and the project's dependency authority `pyproject.toml`:

```bash
make bootstrap
conda activate traffic
make lint
make test
make smoke
make oncall-demo
```

`make test` runs all backend and frontend behavior checks. It starts and removes an isolated PostgreSQL container automatically when `TRAFFIC_TEST_DSN` is absent, so Docker must be running; an explicit DSN can point to a disposable test database instead. Real database cases are not silently skipped. `make test-unit` runs the faster source/API component checks without requiring that database. `make smoke` creates a real isolated Compose project for Kafka/PostgreSQL/API/browser-serving acceptance, duplicates/old events, dataset/mode isolation and restart persistence. `make oncall-demo` uses an isolated project for the controlled user-journey failure, delivered alert, bounded recovery and resolved incident evidence. The full smoke creates an additional stack and requires adequate free Docker VM memory. If this repository is already running and Docker exposes less than 5 GiB, it fails before creating another stack; a 6 GiB or larger Docker allocation is recommended for concurrent acceptance. This safeguard does not guarantee free capacity or stop existing services. Use `make test` or `make test-unit` while capacity is limited. Read their actual output and the [validation ledger](docs/evidence/rubric-validation.md): the commands being documented does not mean they passed. They must not stop unrelated stacks or remove existing application data.

Browser smoke prerequisites (host-side Python and browser tooling are separate from `make up`, which needs Docker only):

```bash
make bootstrap
cd frontend
npm ci
npx playwright install chromium
cd ..
make smoke
```

On a minimal Linux host, Playwright may also require its documented browser system dependencies. `make oncall-demo` uses the same browser prerequisites. Installing Chromium does not start provider polling or train models.

For a frontend production build:

```bash
cd frontend
npm ci
npm run build
```

Optional components:

```bash
make up-ingestion
make up-streaming
make up-inference MODEL_ARTIFACT_KEY=artifacts/models/.../bundle.joblib MODEL_VERSION=7
make up-orchestration
make up-ml
```

Provider profiles require permitted sources/credentials and actual coverage verification. Starting the streaming profile is not evidence that a Flink feature job was submitted/running. Inference requires an independently evaluated notebook-produced artifact; it does not train a model. Generic code supports +240, but MVP acceptance is +15/+60.

Inspect declared registry/dataset readiness without contacting providers:

```bash
conda run -n traffic python -m cognitive_traffic.monitoring.registry_report
```

This deterministic config report hashes input files; mapping, dataset acquisition and rights remain unverified unless separate evidence establishes them. Twelve anchors do not mean twelve independent provider segments or citywide coverage.

Replay archives through the shared raw transport:

```bash
make replay START=2026-08-01T00:00:00Z END=2026-08-08T00:00:00Z DATASET=traffic
```

Replay/reprocessing and benchmark identities must remain distinct from live current state. Verify sink enforcement using smoke evidence rather than inferring it from a producer flag.

## Repository and model workflow

| Path | Responsibility |
|---|---|
| `src/cognitive_traffic/ingestion` | Provider polling/raw provenance |
| `src/cognitive_traffic/streaming` | Kafka contracts, normalization, event-time processing, replay and serving |
| `src/cognitive_traffic/storage` | Object storage, PostgreSQL, initialization and persistence |
| `src/cognitive_traffic/forecasting` | Shared features/baselines/evaluation/training helpers and artifact inference |
| `src/cognitive_traffic/monitoring`, `operations` | Correlated telemetry, journey probe and restricted recovery |
| `notebooks/exploration.ipynb` | Model audit/train/evaluate/export execution |
| `orchestration/dags` | Preparation, DQ/replay and notebook-artifact review |
| `frontend`, `infra`, `tests` | Operator UI, container/configuration and verification |

Training/evaluation/candidate selection execute in notebooks and reuse package helpers. Airflow does not train or automatically move serving aliases. Missing leakage/DQ/schema evidence fails artifact review closed. The notebook has no committed training outputs and requires lawful acquired data and clean-kernel execution before any model-quality claim. Store generated datasets/models under `.local/` or object storage/MLflow, never in source control.

Contracts distinguish event, ingestion and availability time. Serving eligibility, idempotency, monotonic updates, redaction and recovery are implementation properties with explicit tests; field coverage, end-to-end learned forecasting quality, human reviews and hosted operation require their own evidence. Use the tracker/ledger for the current verified boundary.
