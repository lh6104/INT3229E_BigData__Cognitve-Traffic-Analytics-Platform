# Render Demo Deployment Design

Date: 2026-10-27. Status: proposed for user review. This is a contest demo deployment, not production hosting.

## Goal

Provide a public URL with a working Cognitive Traffic UI and API for the DataTalks.Club AI Dev Tools Project 1 deployment criterion. Keep scope to the existing 12 configured monitoring points. Do not start provider polling or claim live coverage, forecasts, or measurements without evidence.

## GitHub repository description

Proposed short description (under GitHub's description limit):

> Data engineering platform prototype for operator-focused traffic monitoring across 12 configured points in Hanoi and Ho Chi Minh City, with React, FastAPI, PostgreSQL, and replayable event processing.

This describes implemented structure and the configured scope without implying verified provider data or learned model quality.

## Hosting shape

Use a Render Blueprint (`render.yaml`) to define three resources:

1. `traffic-api`: public Render web service built from `infra/docker/api.Dockerfile`, with `/system/health` as its health check. Its start command runs the existing idempotent PostgreSQL bootstrap before Uvicorn, binding to Render's `$PORT`.
2. `traffic-dashboard`: Render web service built from `infra/docker/frontend.Dockerfile`. It uses the existing Node server and same-origin `/api` proxy. `API_UPSTREAM` references the API service's external hostname and the Node adapter supplies HTTPS when the scheme is omitted. This lets the free dashboard service reach the free API service without relying on private traffic to a free service.
3. `traffic-demo-db`: Render PostgreSQL, with its private connection string passed to the API as `POSTGRES_DSN`.

Choose Free plans for the contest demo. Do not deploy Kafka, Flink, MinIO, Airflow, Redis, MLflow, ingestion workers, or monitoring backends. The API/UI path and PostgreSQL are sufficient for the deployment rubric. Database bootstrap registers the 12 configured anchors; absent observations remain explicitly missing/unobserved.

## Constraints and failure behavior

- Free Render web services spin down when idle and can have a cold start; the evaluator must allow the first request time to complete.
- Free Render Postgres expires after 30 days and has no backups. Treat it as disposable contest-demo state, not durable project storage.
- Do not add source API credentials or commit secrets to the Blueprint.
- Health is unhealthy until PostgreSQL is reachable; failed bootstrap should prevent a false healthy deployment.
- No provider polling or synthetic traffic readings are introduced.

## Acceptance evidence

Before claiming deployment is complete, record the public dashboard URL and commit, then verify:

- dashboard root loads over HTTPS;
- `/api/system/health` reports healthy;
- the monitoring page shows all 12 configured points and distinguishes unobserved state from measured state;
- browser requests use the dashboard's same-origin `/api` route;
- first-request cold start and service logs are inspected.

The repo can contain a validated Blueprint and deployment steps before a Render resource exists. That is deployment configuration, not evidence of a hosted app. Actual hosting requires the user's Render workspace and authorized GitHub connection; repository metadata such as the GitHub About description also requires repository-owner write access.
