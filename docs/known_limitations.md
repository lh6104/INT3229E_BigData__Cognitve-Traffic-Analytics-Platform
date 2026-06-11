# Known Limitations

This project is ready for a capstone/demo walkthrough, but it is not a production traffic platform. The points below should be stated clearly in reports and presentations.

## Data Coverage

- Hanoi traffic coverage is currently about 75 segments with real geometry.
- The dataset is not full-city coverage and does not cover every road, ward, or district in Hanoi.
- The local data is built from controlled crawls and generated Silver/Gold artifacts, not a continuously operating citywide feed.

## Forecasting

- The Forecast page uses real backend inference through the default LightGBM model bundle.
- The current model input schema has 67 required features.
- Local Gold data still requires partial feature fill for demo inference. A typical Hanoi segment such as `HN_005` fills about 15 of 67 features.
- The UI exposes this as `Partial feature fill`; predictions should be presented as prototype model outputs, not final operational forecasts.

## Predicted Hotspots

- `/hotspots/predicted` is a demo predictive analytics endpoint.
- It applies transparent rules to model-predicted speed:
  - predicted speed below 20 km/h,
  - predicted speed below half free-flow speed,
  - or predicted speed dropping more than 30 percent from current speed.
- It is not a production risk engine, incident prediction service, or calibrated traffic-control decision system.

## Monitoring And System Health

- Monitoring and System Health views still contain demo/static elements.
- They are useful for explaining the intended observability surface, but they are not wired to full infrastructure telemetry.

## Streaming And Infrastructure

- The architecture includes Kafka, Redis, Postgres, MinIO, Trino, Airflow, and related big-data components.
- In the current demo state, the reliable path is local/batch-oriented processing over `raw/` and `data/`.
- Real streaming ingestion and full infrastructure integration are not yet productionized.

## Model Artifacts

- Model artifacts are not committed to normal Git history.
- `cta_training_outputs/` and `result/cta_training_outputs_balanced_v3_latest/` are ignored to avoid storing large binary artifacts in Git.
- Use Git LFS, object storage, or a model registry for long-term artifact management.

## Frontend Fallbacks

- Live Map has explicit fallback behavior for demo continuity.
- Fallback data is labeled and should not be described as live API data.

## External Services

- Live crawling depends on external API keys and quotas.
- `.env.local` must remain local and must not be committed or printed in logs.
