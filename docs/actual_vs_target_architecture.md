# Actual vs Target Architecture

| Component | Demo hiện tại | Production target | Status |
|---|---|---|---|
| API | FastAPI đọc local artifacts và Gold data | FastAPI + cache/service layer + deployment hardening | Demo ready |
| Frontend | React/TanStack/Vite local dashboard | Deployed frontend with monitored API integration | Demo ready |
| Storage | Local CSV/Parquet/JSONL under `raw/` and `data/` | MinIO/Iceberg/Trino lakehouse | Partial/planned |
| Streaming | Mini-demo/local design when Kafka is running | Kafka producers/consumers with offsets, lag, DLQ, and orchestration | Partial |
| ML | Local joblib artifact loaded by API | Model registry + artifact versioning + monitoring | Prototype |
| Forecast | API inference with feature coverage reporting and partial fill | Full feature schema with reliability gating | Prototype |
| Predicted hotspots | Prototype explainable risk scoring over forecast output | Calibrated risk engine with ground-truth validation | Prototype |
| Monitoring | `/system/status`, `/monitoring/*`, generated benchmark/smoke reports | Telemetry stack with p95, resource usage, alerting, and SLA tracking | Partial |
| NewsCrawler | Phase 1 crawler/data models/event features | Scheduled crawler with quality monitoring and geocoding SLAs | Partial |

## Safe interpretation

The reliable demo path is local/batch-oriented. Kafka/streaming is demonstrated through a minimal path when Kafka is available, and otherwise remains target architecture evidence. The project should not be described as a production traffic-control system.
