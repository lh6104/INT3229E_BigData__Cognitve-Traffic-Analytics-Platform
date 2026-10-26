# Cognitive Traffic

Cognitive Traffic is a replayable traffic-stream processing and forecasting system. Kafka is the event log, MinIO/S3 is durable history, PostgreSQL is the operational read store, and the same point-in-time feature logic is used for replay, training, and inference.

The project is deliberately narrow: ingest traffic, weather, and road-event context; process event time correctly; forecast road speeds at 15, 60, and 240 minutes; and expose operational results through a small API and dashboard.

## Repository map

```text
src/cognitive_traffic/
  ingestion/       provider polling and raw events
  streaming/       Kafka topics, normalization, event-time processing, replay
  forecasting/     point-in-time features, evaluation, training, inference
  storage/         MinIO/S3, PostgreSQL, and Redis boundaries
  api/             operational FastAPI application
  contracts/       versioned Pydantic event schemas
  monitoring/      stream quality metrics
  settings.py      YAML and environment configuration
orchestration/dags/ offline training, quality, replay, and compaction
frontend/           traffic, forecasting, and platform views
configs/            development, training, and source configuration
infra/              Docker images and service initialization
tests/              unit, integration, streaming, and forecasting behavior
```

Generated datasets, model binaries, and reports are not source code. Local scratch files belong in `.local/`; production artifacts belong in MinIO/S3 and MLflow.

## Set up Python 3.11

The bootstrap script creates the requested `traffic` Conda environment when needed and installs this package from the single dependency authority, `pyproject.toml`.

```bash
make bootstrap
conda activate traffic
```

Equivalent manual setup:

```bash
conda create --name traffic python=3.11 pip -y
conda run --name traffic python -m pip install -e ".[dev]"
```

## Run locally

```bash
cp .env.example .env
make up
make api
```

Optional runtime paths are explicit Compose profiles:

```bash
make up-ingestion
make up-streaming
make up-inference MODEL_ARTIFACT_KEY=artifacts/models/.../bundle.joblib MODEL_VERSION=7
make up-orchestration
docker compose --profile dashboard up -d frontend
```

Replay archived events through the same raw topics used by live ingestion:

```bash
make replay START=2026-08-01T00:00:00Z END=2026-08-08T00:00:00Z DATASET=traffic
```

## Verify

```bash
make lint
make test
cd frontend && npm run build
docker compose config --quiet
```

Inspect the fixed 12-point registry and declared dataset readiness without
calling traffic providers:

```bash
conda run -n traffic python -m cognitive_traffic.monitoring.registry_report
```

The report hashes the input configs and labels provider mapping and dataset
rights/acquisition status as unverified where they have not been independently
confirmed. It is a configuration check, not evidence of live coverage.

The API exposes traffic state, history, forecasts, hotspots, alerts, model metrics, data quality, and health. OpenAPI is available at <http://localhost:8000/docs>.

## Engineering guarantees

- Contracts distinguish `event_time`, `ingested_at`, and `available_at` and reject naive timestamps.
- Content-derived event IDs make retries and replay deterministic.
- Traffic is keyed by `road_id`; invalid records have an explicit dead-letter contract.
- Point-in-time features exclude future or unavailable values.
- Walk-forward evaluation compares persistence, historical/seasonal medians, Ridge, and LightGBM quantiles.
- Promotion requires baseline improvement, acceptable peak-hour error, clean leakage/data-quality checks, and serving compatibility.
- MLflow and object storage own model lineage and artifacts; no model binaries live in this repository.

See [docs/architecture.md](docs/architecture.md) for the system boundaries and replay semantics.
