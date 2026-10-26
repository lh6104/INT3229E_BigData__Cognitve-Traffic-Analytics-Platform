# Cognitive Traffic Analytics Platform — Project Resume

> **Course:** INT3229E — Big Data\
> **Repository:** `INT3229E_BigData__Cognitve-Traffic-Analytics-Platform`\
> **Version:** 0.3.0 · Python 3.11 · Node 22

---

## 1. Project Overview

**Cognitive Traffic** is a **replayable, real-time traffic stream-processing and ML forecasting platform** designed to ingest live traffic, weather, and road-event data from Vietnamese cities (Hanoi & Ho Chi Minh City), process them through event-time-correct streaming pipelines, and forecast road speeds at **15-minute, 60-minute, and 4-hour horizons** using quantile regression models (LightGBM). Results are exposed via a RESTful API and an interactive React dashboard.

### Core Capabilities

| Capability | Description |
|---|---|
| **Multi-source ingestion** | Traffic (TomTom API), weather (OpenWeatherMap API), road events (Vietnamese RSS news feeds) |
| **Kappa-style streaming** | Live and historical events share the same Kafka topics and transformation logic |
| **Event-time processing** | Watermark-based late-event handling, deterministic replay from S3 archives |
| **ML forecasting** | Multi-horizon quantile predictions (p10/p50/p90) with walk-forward evaluation |
| **Model lifecycle** | MLflow tracking, automated promotion gates, champion/challenger registry |
| **Operational dashboard** | React + Leaflet live map, forecast charts, monitoring panels |
| **Data lake** | Partitioned Parquet on MinIO/S3 with dataset manifests and compaction |

---

## 2. Architecture

The system follows a **Kappa architecture** — there is no separate batch layer. All events (live or replayed) flow through the same Kafka topics and processing logic.

### System Boundaries

| Component | Owns | Does Not Own |
|---|---|---|
| **Kafka** | Live event log, per-road ordering, replay transport | Long-term analytical storage |
| **Apache Flink** | Event-time validation, state, windows, joins, features | Scheduled training |
| **MinIO/S3** | Raw archive, canonical Parquet, ML datasets, model artifacts | Low-latency API queries |
| **Apache Airflow** | Dataset builds, audits, replay coordination, training, promotion, compaction | Individual events |
| **PostgreSQL** | Operational road, forecast, alert, outcome and model state | Raw history |
| **Redis** | Hot/current state cache | Source of truth |
| **MLflow** | Experiments, lineage, model versions and promotion | Feature computation |

### Data Flow (Topic Contract)

```
traffic.raw.v1           weather.raw.v1          news.raw.v1
      │                        │                       │
      ▼                        ▼                       ▼
traffic.observation.v1   weather.observation.v1   road.event.v1
      └────────────────────────┼───────────────────────┘
                               ▼
                     traffic.features.v1
                               ▼
                    traffic.forecasts.v1
                          │          │
                          ▼          ▼
               traffic.alerts.v1  prediction.outcomes.v1

               dead_letter.v1  ← invalid records from any stage
```

All 11 Kafka topics are versioned (`*.v1`). Traffic topics use `road_id` as the partition key.

### Data Lake Layout

```
s3://cognitive-traffic/
├── raw/{traffic,weather,news}/event_date=YYYY-MM-DD/city=.../
├── canonical/{traffic,weather,events}/event_date=YYYY-MM-DD/city=.../
├── ml/{features,training,predictions,outcomes,manifests}/...
└── artifacts/{mlflow,models,adjacency}/...
```

---

## 3. Technology Stack

### Backend (Python 3.11)

| Category | Technologies |
|---|---|
| **Core** | Pydantic v2 (contracts & settings), PyYAML, pydantic-settings |
| **API** | FastAPI, Uvicorn, structlog, prometheus-client |
| **Streaming** | confluent-kafka (Python client), Apache Flink 1.20.2 (PyFlink) |
| **ML/Forecasting** | LightGBM, scikit-learn (Ridge, StandardScaler), pandas, numpy, PyArrow, joblib |
| **Experiment Tracking** | MLflow 2.16.2 |
| **Storage** | boto3 (S3/MinIO), psycopg v3 (PostgreSQL), redis-py |
| **Ingestion** | requests, feedparser (RSS) |
| **Orchestration** | Apache Airflow 2.10.5 |
| **Dev Tools** | pytest, pytest-cov, ruff (linter) |

### Frontend (TypeScript / React 19)

| Category | Technologies |
|---|---|
| **Framework** | React 19, Vite 7, TanStack Router, TanStack React Query |
| **Mapping** | Leaflet + react-leaflet |
| **Charts** | Recharts v3 |
| **Styling** | Tailwind CSS v4 |
| **Utilities** | Zod v4, Lucide React (icons), SWR |

### Infrastructure (Docker Compose)

| Service | Image / Build |
|---|---|
| **Kafka** | Confluent CP-Kafka 7.7.1 (KRaft mode, no ZooKeeper) |
| **MinIO** | minio/minio (S3-compatible object store) |
| **PostgreSQL** | postgres:16-alpine |
| **Redis** | redis:7.4-alpine |
| **MLflow** | Custom Dockerfile (backed by PostgreSQL + S3) |
| **Flink** | Custom Dockerfile (JobManager + TaskManager) |
| **Airflow** | Custom Dockerfile (LocalExecutor, PostgreSQL backend) |
| **Prometheus** | prom/prometheus:v3.13.1 |
| **Frontend** | node:22-alpine (dev server) |

### CI/CD

- **GitHub Actions** (`ci-light.yml`): Python lint (ruff), compile check, pytest, frontend build on every push/PR

---

## 4. Repository Structure

```
├── src/cognitive_traffic/          # All production Python code
│   ├── ingestion/                  # Provider polling (traffic, weather, news)
│   │   ├── traffic.py              # TomTom API poller
│   │   ├── weather.py              # OpenWeatherMap API poller
│   │   └── news.py                 # Vietnamese RSS feed crawler
│   ├── streaming/                  # Kafka topics, normalization, replay
│   │   ├── topics.py               # Topic registry (11 topics)
│   │   ├── producers.py            # Contract-aware Kafka producer
│   │   ├── processors.py           # Normalizer, archiver, Flink feature job
│   │   └── replay.py               # S3→Kafka historical replay
│   ├── forecasting/                # ML pipeline
│   │   ├── features/               # Point-in-time feature builder
│   │   │   ├── traffic.py          # Feature registry + builder (9 features)
│   │   │   └── spatial.py          # Neighbor road mean speed
│   │   ├── baselines.py            # Persistence, HistoricalMedian, SeasonalMedian
│   │   ├── evaluation.py           # Walk-forward splitter, metrics, pinball loss
│   │   ├── training.py             # LightGBM quantile training + MLflow + promotion
│   │   └── inference.py            # Real-time Kafka→forecast service
│   ├── storage/                    # External persistence boundaries
│   │   ├── object_store.py         # S3/MinIO: Parquet I/O, manifests, compaction
│   │   ├── postgres.py             # TrafficRepository (all SQL queries)
│   │   └── redis.py                # Hot-state cache
│   ├── contracts/                  # Versioned Pydantic event schemas
│   │   ├── events.py               # EventMetadata, DeadLetterEvent, RoadEvent
│   │   ├── traffic.py              # TrafficObservation
│   │   ├── weather.py              # WeatherObservation
│   │   └── forecasts.py            # TrafficFeatures, Forecast, PredictionOutcome
│   ├── monitoring/                 # Stream quality metrics
│   │   ├── metrics.py              # StreamQualityWindow, QualitySnapshot
│   │   └── prometheus.py           # Worker-level Prometheus counters
│   ├── api/main.py                 # FastAPI application (10 endpoints)
│   └── settings.py                 # YAML + env configuration loader
├── orchestration/dags/             # Airflow DAGs
│   ├── train_forecast.py           # Weekly model lifecycle (train → evaluate → promote)
│   ├── data_quality.py             # Daily data-quality gate
│   ├── replay.py                   # On-demand historical replay
│   └── compact_lake.py             # Nightly Parquet compaction
├── frontend/                       # React dashboard
│   └── src/
│       ├── routes/_app/            # Page routes (live-map, forecast, monitoring)
│       ├── components/             # Dashboard, LiveMap, Layout, UI components
│       └── hooks/                  # Custom React hooks
├── configs/                        # YAML configuration
│   ├── development.yaml            # Dev environment settings
│   ├── sources.yaml                # Monitoring points (12 road segments) + RSS feeds
│   └── training.yaml               # ML hyperparameters & promotion thresholds
├── infra/                          # Infrastructure definitions
│   ├── docker/                     # 5 Dockerfiles (API, streaming, Flink, Airflow, MLflow)
│   ├── kafka/create-topics.sh      # Topic initialization script
│   ├── postgres/schema.sql         # 9 tables + 1 view + indexes
│   ├── flink/                      # Flink SQL + Java UDFs
│   └── prometheus/                 # Prometheus scrape config
├── tests/                          # Test suite
│   ├── unit/                       # Contracts, monitoring, storage tests
│   ├── integration/                # API integration tests
│   ├── streaming/                  # Normalization, processor tests
│   └── forecasting/                # Feature, training, governance tests
├── notebooks/exploration.ipynb     # Data exploration notebook
├── docker-compose.yml              # Full stack orchestration (15 services)
├── Makefile                        # Developer workflow commands
├── pyproject.toml                  # Single dependency authority
└── .github/workflows/ci-light.yml  # CI pipeline
```

**Scale:** ~53 Python files, ~19 TypeScript/TSX files

---

## 5. Data Ingestion Layer

### 5.1 Traffic Data (TomTom)
- **API:** TomTom Traffic Flow v4
- **Polling interval:** 300s (configurable)
- **Coverage:** 12 road segments across Hanoi (6) and HCMC (6)
- **Fields:** `speed_kmh`, `free_flow_speed_kmh`, `confidence`
- **Output topic:** `traffic.raw.v1`

### 5.2 Weather Data (OpenWeatherMap)
- **API:** OpenWeatherMap Current Weather
- **Polling interval:** 900s (configurable)
- **De-duplication:** Unique weather cells per monitoring point
- **Fields:** `temperature_c`, `precipitation_mm`, `wind_speed_kmh`, `condition`
- **Output topic:** `weather.raw.v1`

### 5.3 Road Events (RSS News)
- **Sources:** VnExpress, Tuoi Tre, Dan Tri, VietnamNet (traffic/current affairs feeds)
- **Polling interval:** 600s (configurable)
- **Processing:** feedparser → event classification (accident, flood, road_work, closure, etc.)
- **Output topic:** `news.raw.v1`

---

## 6. Streaming & Event Processing

### 6.1 Normalization
- Consumes raw topics → validates → produces canonical events
- Maps provider-specific field names to platform contracts
- Invalid records → `dead_letter.v1` with failure reason and original payload

### 6.2 Raw Archive
- Batch-consumes raw topics (500 messages/batch)
- Writes Parquet files to S3, partitioned by `event_date` and `city`
- Enables deterministic replay of historical periods

### 6.3 Event-Time Feature Processor
- **Python reference processor:** Watermark-based late event detection, deduplication, 60-minute sliding window
- **Flink production job:** SQL-based rolling window features with custom Java UDFs (`Mean15m`, `Mean30m`)
- Both share the same semantic guarantees

### 6.4 Replay System
- Reads archived Parquet from S3, filters by time range, re-publishes to raw topics
- CLI: `make replay START=... END=... DATASET=traffic`
- Same normalization and feature pipelines process replayed events identically

### 6.5 Time Semantics
- **`event_time`:** When the source condition occurred
- **`ingested_at`:** When the platform received the record
- **`available_at`:** Earliest instant a feature was legitimately knowable
- Naive (timezone-unaware) timestamps are rejected at the contract level
- Content-derived deterministic event IDs (SHA-256) make retries and replay idempotent

---

## 7. Event Contracts (Pydantic Schemas)

All schemas use `Pydantic v2` with `extra="forbid"`, `frozen=True`, and strict timezone validation.

| Contract | Key Fields |
|---|---|
| **TrafficObservation** | `road_id`, `city`, `speed_kmh`, `free_flow_speed_kmh`, `confidence`, `available_at` |
| **WeatherObservation** | `weather_cell_id`, `city`, `temperature_c`, `precipitation_mm`, `wind_speed_kmh`, `condition` |
| **RoadEvent** | `road_id`, `city`, `event_type` (enum), `severity` (0–3), `confidence`, `expires_at` |
| **TrafficFeatures** | `road_id`, `prediction_time`, 9 engineered features |
| **Forecast** | `road_id`, `prediction_time`, `target_time`, `horizon_minutes`, `p10/p50/p90_speed_kmh` |
| **PredictionOutcome** | `prediction_id`, `forecast_speed_kmh`, `actual_speed_kmh`, `absolute_error_kmh` |
| **DeadLetterEvent** | `original_topic`, `failure_reason`, `failed_at`, `payload` |

---

## 8. ML Forecasting Pipeline

### 8.1 Feature Engineering (9 Point-in-Time Features)

| Feature | Source | Lookback |
|---|---|---|
| `speed_kmh` | Traffic | Current |
| `speed_mean_15m` | Traffic | 15 min |
| `speed_mean_30m` | Traffic | 30 min |
| `speed_mean_60m` | Traffic | 60 min |
| `speed_std_60m` | Traffic | 60 min |
| `speed_change_kmh` | Traffic | 60 min |
| `precipitation_mm` | Weather | 180 min |
| `event_severity` | Road events | 180 min |
| `neighbor_mean_speed_kmh` | Traffic (spatial) | 15 min |

All features enforce `available_at <= prediction_time` (no future leakage).

### 8.2 Baseline Models
- **Persistence:** Predicts current speed
- **Historical Median:** Road-level or global median
- **Seasonal Median:** Grouped by `(road_id, weekday, hour)`
- **Ridge Regression:** StandardScaler + Ridge (α=1.0)

### 8.3 LightGBM Quantile Models
- **Objective:** Quantile regression
- **Quantiles:** p10, p50, p90 (uncertainty estimation)
- **Horizons:** 15 min, 60 min, 240 min
- **Hyperparameters:** 400 estimators, lr=0.04, 31 leaves, min_child=40, subsample=0.9

### 8.4 Evaluation
- **Walk-forward cross-validation:** Expanding window (28-day minimum train, 7-day validation, 7-day step)
- **Metrics:** MAE, RMSE, Bias, Pinball Loss
- **Sliced evaluation:** Peak vs off-peak hours, weekday vs weekend, city, road category, weather condition

### 8.5 Model Promotion Gate
Automated checks before promoting a candidate to champion:
- Candidate must beat persistence baseline
- Candidate must not regress beyond 2% of champion MAE
- Peak-hour MAE must not exceed 12.0 km/h
- Point-in-time leakage checks must pass
- Data-quality gate must pass
- Model signature must be compatible with serving

### 8.6 Inference Service
- Consumes `traffic.features.v1` from Kafka
- Loads model bundle from S3 (joblib)
- Produces forecasts for all 3 horizons per feature event
- Includes congestion probability estimation via quantile CDF interpolation

---

## 9. Database Schema (PostgreSQL)

9 tables + 1 view:

| Table | Purpose |
|---|---|
| `roads` | Road segment registry (id, city, name, category, geometry) |
| `traffic_observations` | Historical speed observations (indexed by road + time) |
| `traffic_current` | Latest state per road (one row per road) |
| `forecasts` | Speed predictions with quantiles and congestion probability |
| `forecast_hotspots` (view) | Roads with congestion_probability ≥ 0.5 |
| `alerts` | Active/acknowledged/resolved traffic alerts |
| `prediction_outcomes` | Forecast vs actual comparisons |
| `model_versions` | Champion/candidate/archived model registry |
| `model_performance` | Windowed MAE/RMSE/Bias per model version |
| `data_quality_metrics` | Stream health (invalid rate, duplicates, late events, freshness) |

---

## 10. REST API (FastAPI)

**Base URL:** `http://localhost:8000` · **OpenAPI docs:** `/docs`

| Endpoint | Method | Description |
|---|---|---|
| `/roads` | GET | List road segments (optional city filter) |
| `/traffic/current` | GET | Current speed per road |
| `/traffic/history` | GET | Historical observations for a road (up to 10,000) |
| `/forecasts` | GET | Speed forecasts (filter by road, horizon) |
| `/hotspots` | GET | Top 50 congestion hotspots |
| `/alerts` | GET | Traffic alerts (active only by default) |
| `/models/current` | GET | Current champion model metadata |
| `/models/metrics` | GET | Model performance metrics |
| `/system/data-quality` | GET | Stream quality metrics |
| `/system/health` | GET | Health check (PostgreSQL dependency status) |
| `/metrics` | GET | Prometheus metrics (internal) |

Features: CORS for frontend, request/response metrics (Counter + Histogram), structured JSON logging.

---

## 11. Frontend Dashboard

**Stack:** React 19 + Vite 7 + TanStack Router + Tailwind CSS v4

### Pages
| Route | Description |
|---|---|
| **Live Map** | Leaflet map showing real-time traffic state on road segments |
| **Forecast** | Speed forecast charts with quantile intervals (p10/p50/p90) |
| **Monitoring** | Platform health, data quality metrics, model performance |

### Components
- `LiveMapView` — Interactive Leaflet map with color-coded speed markers
- `AppSidebar` — Navigation sidebar
- `TopBar` — Header bar
- `PageHeader` / `PlaceholderPage` — Shared UI primitives

---

## 12. Orchestration (Airflow DAGs)

| DAG | Schedule | Description |
|---|---|---|
| `traffic_model_lifecycle_v1` | Manual trigger | Validate manifest → Train with walk-forward → Apply promotion gate → Promote to champion |
| `traffic_data_quality_v1` | Daily 01:15 | Check latest stream quality window against invalid-event threshold (5%) |
| `traffic_historical_replay_v1` | Manual trigger | Replay archived events through Kafka for a given time range |
| `traffic_lake_compaction_v1` | Daily 02:30 | Compact small Parquet objects per date/city partition |

---

## 13. Monitoring & Observability

### Prometheus Metrics
- `traffic_api_requests_total` — HTTP request counter (method, path, status)
- `traffic_api_request_seconds` — Request latency histogram
- `traffic_events_received_total` — Kafka events received per worker/topic
- `traffic_events_invalid_total` — Rejected events per worker/topic
- `normalizer_events_processed_total` — Normalizer outcomes (accepted/invalid)
- `archive_objects_written_total` — Parquet objects written by archiver

### Stream Quality Tracking
- Events received, invalid, duplicate, and late counts per window
- Freshness P95 (seconds)
- Road coverage (roads reporting vs expected)

---

## 14. Data Sources & Coverage

### Monitoring Points (12 road segments)

**Hanoi (6):**
- HN_HK_001 (Hoàn Kiếm), HN_BD_001 (Ba Đình), HN_CG_001 (Cầu Giấy)
- HN_TX_001 (Thanh Xuân), HN_RR3_001 (Ring Road 3), HN_VNG_001 (Vĩnh Ngọc)

**Ho Chi Minh City (6):**
- HCMC_D1_001 (District 1), HCMC_D3_001 (District 3), HCMC_BT_001 (Bình Thạnh)
- HCMC_TD_001 (Thủ Đức), HCMC_Q7_001 (District 7), HCMC_CL_001 (Cat Lai)

### RSS News Sources
- VnExpress (giao-thong), Tuoi Tre (giao-thong), Dan Tri (thoi-su), VietnamNet (thoi-su)

---

## 15. Engineering Guarantees

1. **Temporal correctness:** Contracts distinguish `event_time`, `ingested_at`, and `available_at`; naive timestamps are rejected
2. **Idempotent processing:** Content-derived SHA-256 event IDs + DB uniqueness constraints make retries and replay deterministic
3. **Road-keyed partitioning:** Traffic is keyed by `road_id` for per-road ordering
4. **Dead-letter handling:** Invalid records are explicitly routed with failure reason and original payload
5. **Point-in-time features:** Exclude future or unavailable values (`available_at <= prediction_time`)
6. **Walk-forward evaluation:** Compares persistence, historical/seasonal medians, Ridge, and LightGBM quantiles
7. **Promotion gates:** Require baseline improvement, acceptable peak-hour error, clean leakage/data-quality checks, and serving compatibility
8. **Artifact lineage:** MLflow and S3 own model lineage — no model binaries in the repository

---

## 16. Development & Operations

### Quick Start
```bash
make bootstrap          # Create Conda environment (Python 3.11)
conda activate traffic
cp .env.example .env    # Configure API keys
make up                 # Start core stack (Kafka, MinIO, PostgreSQL, Redis, MLflow, normalizer, archiver, API)
make api                # Start API with hot-reload
```

### Optional Services
```bash
make up-ingestion       # Start traffic, weather, news pollers
make up-streaming       # Start Flink feature processor
make up-inference MODEL_ARTIFACT_KEY=... MODEL_VERSION=...
make up-orchestration   # Start Airflow
```

### Verification
```bash
make lint               # Ruff lint + compile check
make test               # pytest
cd frontend && npm run build  # Frontend build check
docker compose config --quiet # Compose validation
```

### CLI Entry Points
```
traffic-ingest    → cognitive_traffic.ingestion.traffic:run
weather-ingest    → cognitive_traffic.ingestion.weather:run
news-ingest       → cognitive_traffic.ingestion.news:run
traffic-stream    → cognitive_traffic.streaming.processors:main
traffic-replay    → cognitive_traffic.streaming.replay:main
traffic-forecast  → cognitive_traffic.forecasting.inference:run
```

---

## 17. Deliberate Exclusions

| Technology | Reason |
|---|---|
| Neo4j | Bounded road-neighbor mappings are sufficient for spatial features |
| Apache Spark | Flink handles live/replay transforms; PyArrow handles bounded Parquet datasets |
| Apache Iceberg | Not needed until atomic table updates, snapshots, or partition evolution become requirements |
| Trino / Data Warehouse | PostgreSQL + direct Parquet training scans cover current query patterns |
| Clustering layer | No product requirement currently depends on clustering |

---

## 18. Configuration

### Environment Variables
| Variable | Purpose |
|---|---|
| `TOMTOM_API_KEY` | TomTom Traffic Flow API key |
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker address |
| `POSTGRES_DSN` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection URL |
| `MLFLOW_TRACKING_URI` | MLflow server URL |
| `OBJECT_STORE_URI` | S3 bucket URI |
| `S3_ENDPOINT_URL` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` | MinIO/S3 credentials |
| `MODEL_ARTIFACT_KEY` / `MODEL_VERSION` | Deployed model coordinates |

### Training Configuration (`configs/training.yaml`)
- Horizons: 15, 60, 240 minutes
- Quantiles: 0.1, 0.5, 0.9
- Minimum training window: 28 days
- Validation window: 7 days
- Maximum champion regression: 2%
- Maximum peak-hour MAE: 12.0 km/h

---

## 19. Testing Strategy

| Layer | Files | Coverage |
|---|---|---|
| **Unit** | `test_contracts.py`, `test_monitoring.py`, `test_storage.py` | Event schema validation, quality windows, object store |
| **Integration** | `test_api.py` | API endpoint responses |
| **Streaming** | `test_normalization.py`, `test_processors.py`, `flink_smoke.sql` | Normalizer logic, event-time processor, Flink SQL |
| **Forecasting** | `test_features.py`, `test_training.py`, `test_model_governance.py` | Feature builder, training pipeline, promotion gate |

---

## 20. Summary

The **Cognitive Traffic Analytics Platform** is a production-grade Big Data system that demonstrates end-to-end data engineering and machine learning capabilities:

- **Ingestion** of heterogeneous real-time data sources (APIs + RSS feeds)
- **Stream processing** with event-time correctness and replay guarantees (Kafka + Flink)
- **Data lake** architecture with partitioned Parquet storage and lineage manifests (MinIO/S3)
- **ML pipeline** with point-in-time feature engineering, walk-forward evaluation, and automated model governance (LightGBM + MLflow)
- **Operational API** with structured logging, Prometheus metrics, and health monitoring (FastAPI)
- **Interactive dashboard** with live traffic maps and forecast visualization (React + Leaflet + Recharts)
- **Workflow orchestration** for training, quality gates, replay, and maintenance (Airflow)
- **CI/CD** with automated linting, testing, and build verification (GitHub Actions)

The system is designed with clear module boundaries, versioned contracts, deterministic processing semantics, and explicit engineering guarantees throughout.
