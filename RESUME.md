# Cognitive Traffic Analytics Platform — evidence-based project resume

Course: INT3229E — Big Data. Stack: Python 3.11, Kafka, Flink/Python, MinIO/S3, PostgreSQL, FastAPI, React/TypeScript, LightGBM and MLflow. This is a local engineering project with explicit acceptance gates; public hosting is deferred.

## Project problem and scope

Developed a traffic-data platform around exactly 12 configured monitoring anchors across Hanoi and Ho Chi Minh City. The operator journey distinguishes observed traffic from missing/stale/unsupported/error states and retains source, dataset/mode and timestamp provenance. Secondary product targets are +15/+60 point forecasting and bounded departure/route-template comparison, subject to data and evaluation eligibility.

## Implemented source-level work

- Versioned event/measurement contracts, deterministic identifiers, registry validation and dataset-purpose/measurement/unit policies.
- Provider adapters for traffic, weather and RSS, Kafka normalization/replay paths, object-storage archive helpers and operational API/UI modules.
- PostgreSQL serving persistence with eligible live current state, history/idempotency and monotonic-update rules; registry anchors remain available when observations are absent.
- Shared point-in-time feature helpers, persistence/historical/seasonal baselines, Ridge/LightGBM quantile training helpers and duration-based walk-forward evaluation.
- Notebook-only training/evaluation/export workflow using current package imports; artifact-only orchestration review with explicit checksums and externally supplied check references. No automatic champion update.
- Local container integration and operational instrumentation, semantic journey checks and restricted incident recovery components. Verification status is recorded separately from implementation.

These bullets describe repository implementation, not proof that every optional source, feature job or model path has run against live data.

## Architecture and data ownership

| Layer | Responsibility |
|---|---|
| Kafka | Event transport/log and replay path; road-keyed ordering |
| Flink/Python | Event-time processing and feature logic; actual job submission must be verified |
| MinIO/S3 | Raw/history, dataset manifests and model artifacts |
| PostgreSQL | Operational observations/current state, forecasts and incident records |
| FastAPI/React | Operator read journey and explicit unavailable states |
| Notebooks | Model training, evaluation, candidate selection and export |
| Airflow | Dataset preparation, audits/replay/compaction and notebook-artifact validation |
| MLflow | Experiment/registry lineage when configured and actually used |
| Redis | Optional cache, never source of truth |

Source time, ingestion time and first availability are different. Point anchors are not automatically verified directed physical segments. Weather/RSS are contextual evidence, not proven causes. Sensor adjacency is not a road routing graph. Benchmark/replay/reprocessing results must not be represented as Vietnamese live measurements.

## Verification and suitable CV wording

Use [current validation evidence](docs/evidence/rubric-validation.md) for executed commands, run IDs, service/browser persistence and operational-fault evidence. The old `43ac84e` audit recorded 46 passing tests and working API reads with empty traffic tables; that historical result did not prove full E2E. New source changes require fresh validation.

Suitable claims after checking the linked evidence:

- “Built versioned traffic-data contracts and registry/dataset policies for a 12-point operator-monitoring MVP.”
- “Developed idempotent Kafka-to-PostgreSQL serving and an API/dashboard with explicit missing-data states.”
- “Implemented notebook-based baseline/quantile forecasting evaluation and independent artifact export.”
- Use “Executed isolated Kafka/PostgreSQL/browser persistence and fault-recovery validation” only when the current ledger records those runs passing.

Do not claim production-grade operation, measured throughput/accuracy improvements, calibrated congestion probabilities, a deployed cloud service, three completed human peer reviews or fully verified learned forecasting unless dedicated evidence exists. Unit/ASGI tests, configuration reports, benchmark performance and live integration are distinct evidence classes.

## Remaining product and external gates

Three real human course peer reviews remain in the [review register](docs/reviews/peer-reviews.md). Provider rights/coverage/direction mapping, lawful acquisition, adequate local history, out-of-sample learned-model improvement/calibration and real route geometry/ETA ground truth need separate validation. CV and LargeST flow research are conditional. +240 is generic configuration capability, outside MVP +15/+60 acceptance. Hosting and deployment automation remain deferred.

See [requirements](docs/requirements/cognitive-traffic-mvp-v1.md), [task tracker](docs/tasks/tracker.md), [agent execution evidence](docs/tasks/agent-execution.md), and [README commands](README.md). CI lint/test/build is continuous integration; it is not evidence of automated public dev/prod deployment.
