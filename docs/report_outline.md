# Report Outline

Suggested structure for a 10-page IEEE-style capstone report.

## 1. Introduction

- Urban congestion motivation.
- Why real-time and predictive traffic analytics matter.
- Project objective: local-first cognitive traffic analytics prototype for Hanoi/HCMC.

## 2. Problem Statement

- Current pain points: fragmented traffic data, limited forecasting, weak situational awareness.
- Scope of this prototype.
- Research/engineering questions:
  - How can heterogeneous traffic, weather, and news data be integrated?
  - How can current and predicted congestion be exposed through an operational UI?

## 3. Related Background

- Intelligent transportation systems.
- Big data traffic pipelines.
- Traffic speed forecasting.
- Geospatial visualization and congestion hotspot detection.

## 4. System Architecture

- End-to-end architecture diagram.
- Ingestion, data/raw/Bronze/Silver/Gold layers.
- API and frontend layers.
- Docker-based reproducible Python 3.11 environment.

## 5. Data Sources And Pipeline

- TomTom traffic data.
- Weather data.
- RSS/HTML traffic news data.
- Raw snapshots and generated Silver/Gold features.
- Current Hanoi coverage and geometry availability.

## 6. Traffic Analytics

- Dashboard metrics.
- Live Map GeoJSON segments.
- Alerts and current hotspot detection.
- Local data access strategy.

## 7. Predictive Modeling And Decision Support

- Forecast model artifact and model family as reported by `/traffic/model/status`.
- Prediction horizons: 15 minutes and 60 minutes.
- Feature schema and partial feature fill.
- Model metrics: MAE, RMSE, R2.
- Prototype predicted hotspot risk scoring based on forecast output, speed/free-flow comparison, jam factor, weather, and event context.
- Cognitive loop: traffic + weather + event + segment context -> forecast -> risk score -> explanation -> dashboard/API insight.

## 8. Prototype Implementation

- FastAPI backend endpoints.
- React/TanStack frontend.
- Docker Compose environment.
- Demo flow: Dashboard, Live Map, Alerts, Hotspots, Forecast, Predicted Hotspots API.

## 9. Evaluation

- API smoke tests.
- Unit tests and pipeline tests.
- Frontend build verification.
- Data coverage statistics.
- Model metrics and qualitative demo results.
- `docs/demo_smoke_report.md`, `reports/api_benchmark.md`, and `reports/streaming_demo_report.md` if generated.

## 10. Limitations And Future Work

- Limited Hanoi coverage.
- Partial feature fill in model inference.
- Monitoring uses local status endpoints and generated reports, not a full telemetry stack.
- Streaming integration is not fully productionized; mini-demo evidence is separate from production readiness.
- Future work: larger crawler coverage, model registry, real streaming, calibrated risk engine, deployment hardening.
