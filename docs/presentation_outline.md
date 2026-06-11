# Presentation Outline

Suggested structure for a 60-minute capstone presentation.

## 0-5 min: Motivation

- Urban congestion and operational traffic awareness.
- Goal: combine current-state analytics with predictive speed forecasting.

## 5-10 min: Dataset And Data Sources

- TomTom traffic snapshots.
- Weather and traffic-news sources.
- Current Hanoi demo coverage: about 75 segments with real geometry.
- Raw, Silver, and Gold data layers.

## 10-17 min: Architecture

- Docker-based local-first architecture.
- Ingestion, processing, API, model inference, and frontend.
- Role of Kafka/Redis/Postgres/MinIO/Trino/Airflow in the target architecture.

## 17-25 min: Data Pipeline

- Raw JSONL snapshots.
- Silver cleaned traffic records.
- Gold feature datasets.
- Geometry preservation for map rendering.

## 25-32 min: Dashboard Demo

- Show dashboard summary and trends.
- Explain that core metrics are backed by local Gold data.

## 32-40 min: Live Map Demo

- Show Hanoi traffic segments.
- Show real GeoJSON coverage.
- Select segment and navigate to Forecast.
- Mention explicit fallback behavior if the API is unavailable.

## 40-46 min: Alerts And Hotspots Demo

- Show active alerts.
- Show current hotspot clusters.
- Explain rule thresholds and local traffic state.

## 46-53 min: Forecast And Model Demo

- Open Forecast page.
- Select a real segment such as `HN_005`.
- Show 15-minute and 60-minute predictions.
- Explain LightGBM model, model source, artifact, and feature coverage.
- Point out `Partial feature fill` honestly.

## 53-56 min: Predicted Hotspots

- Open Swagger or use curl for:

```text
/hotspots/predicted?city=hanoi&horizon=15m
```

- Explain demo rules: low predicted speed, low predicted/free-flow ratio, large speed drop.

## 56-59 min: Results

- Tests pass in Docker Python 3.11.
- Frontend build passes.
- Model metrics: MAE around 4.45-4.49 kph, R2 around 0.888.
- Demo coverage and endpoint readiness.

## 59-60 min: Limitations And Q&A

- Coverage is not full-city.
- Some Monitoring/System Health elements remain demo/static.
- Forecast still fills part of the model feature vector.
- Streaming is not fully productionized.
- Q&A.
