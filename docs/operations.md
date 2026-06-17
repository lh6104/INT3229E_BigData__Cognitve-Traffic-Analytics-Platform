# Operations

Start stack:

```bash
make up
```

Run the local end-to-end data path:

```bash
make stream-test
make pipeline
make dq-check
make train
make neo4j-import
make graph-test
make api-smoke
make benchmark
```

Airflow UI runs at `http://localhost:8088` with `admin/admin` by default. Trigger `cta_production_like_local_pipeline`.

The Airflow DAG accepts optional params:

- `raw_dir`: default `raw`
- `output_dir`: default `data`
- `run_id`: default `airflow_manual`

The DAG writes `reports/airflow_run_report.json` and the local pipeline writes `reports/pipeline_run_manifest.json` plus `reports/pipeline_run_manifest.md`.

## Backfill and Incremental Load Policy

The verified local pipeline is currently a full-refresh pipeline over the available `raw/` snapshots. This is intentional for a Junior Data Engineer portfolio project because it keeps the run reproducible and easy to inspect.

The natural incremental keys are:

- traffic/weather: `event_time` normalized into `time_bucket`
- news/events: `published_at_utc` or derived `event_time_start`
- Gold grain: `city + segment_id + time_bucket`

For a production incremental version, the pipeline would filter raw records by `start_date <= event_time < end_date`, rebuild affected time buckets, and rerun DQ on the impacted partitions. Until that is implemented and tested, do not describe the project as having production backfill.

MLflow UI runs at `http://localhost:5000`. Training serves from local joblib artifacts; MLflow is used for tracking, not as a mandatory serving registry.

Neo4j Browser runs at `http://localhost:7474`, default local credentials `neo4j/password`.
