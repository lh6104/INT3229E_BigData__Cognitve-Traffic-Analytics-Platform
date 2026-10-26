# Architecture decisions

## System identity

Cognitive Traffic is a replayable stream-processing and ML forecasting system. The architecture is Kappa-style: live and historical events use the same Kafka topics and transformation logic. S3-compatible object storage is the durable history.

## Responsibilities

| Component | Owns | Does not own |
|---|---|---|
| Kafka | live event log, per-road ordering, replay transport | long-term analytical storage |
| Flink | event-time validation, state, windows, joins, features | scheduled training |
| MinIO/S3 | raw archive, Canonical and ML Parquet, artifacts | low-latency API queries |
| Airflow | dataset builds, audits, replay coordination, training, promotion, compaction | individual events |
| PostgreSQL | operational road, forecast, alert, outcome and model state | raw history |
| Redis | justified hot/current state only | source of truth |
| MLflow | experiments, lineage, model versions and promotion | feature computation |

## Topic contract

All topic names are versioned. Traffic topics use `road_id` as their Kafka key.

```text
traffic.raw.v1              weather.raw.v1             news.raw.v1
      │                            │                          │
      ▼                            ▼                          ▼
traffic.observation.v1      weather.observation.v1      road.event.v1
      └────────────────────────────┼──────────────────────────┘
                                   ▼
                         traffic.features.v1
                                   ▼
                        traffic.forecasts.v1
                              │          │
                              ▼          ▼
                   traffic.alerts.v1  prediction.outcomes.v1
```

Invalid records from any stage are wrapped with the original topic, event ID, reason, failure timestamp, and payload reference, then sent to `dead_letter.v1`.

## Time and replay semantics

- `event_time`: when the source condition occurred.
- `ingested_at`: when the platform received the record.
- `available_at`: earliest instant a feature was legitimately knowable.
- Flink watermarks tolerate bounded out-of-order delivery.
- Records behind the allowed-lateness boundary are measured and routed by policy; they do not silently mutate already-emitted forecasts.
- Deterministic IDs and database uniqueness constraints make replay idempotent.
- Training includes a feature only when `available_at <= prediction_time`; targets occur at `prediction_time + horizon`.

## Data lake

```text
s3://cognitive-traffic/
├── raw/{traffic,weather,news}/event_date=YYYY-MM-DD/city=.../
├── canonical/{traffic,weather,events}/event_date=YYYY-MM-DD/city=.../
├── ml/{features,training,predictions,outcomes}/...
└── artifacts/{mlflow,models,adjacency}/...
```

Partitions match dataset scans: date and city. `road_id` is not a partition. Airflow compacts small streaming objects. Dataset manifests bind a deterministic dataset ID to source windows, schema/feature versions, row counts, and exact object keys.

## Deliberate exclusions

- Neo4j: bounded road-neighbor mappings are sufficient for the spatial feature in `forecasting/features/spatial.py`.
- Spark: Flink handles live/replay transforms and PyArrow handles bounded Parquet datasets.
- Iceberg: add only when atomic table updates, snapshots, or partition evolution become requirements.
- Trino/warehouse: PostgreSQL and direct Parquet training scans cover current query patterns.
- Clustering: no product requirement currently depends on a clustering layer.

## Code ownership

All production Python lives under `src/cognitive_traffic`. Ingestion owns provider calls, streaming owns event normalization and time semantics, forecasting owns model behavior, and storage owns external persistence. Airflow DAGs remain outside the package because they are deployment definitions, not business logic. No parallel `services`, `pipelines`, `ml`, or `domain` layer exists.
