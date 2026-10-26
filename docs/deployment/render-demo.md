# Render contest demo deployment (proposed; not yet hosted)

Date: 2026-10-27. Scope: API, React dashboard, and disposable PostgreSQL only. This is **not production hosting**. A committed Blueprint is **not evidence of a working public URL**.

## Architecture and explicit boundaries

`render.yaml` declares `traffic-api` and `traffic-dashboard` as Free web services and `traffic-demo-db` as Free Render Postgres, all in `singapore`. Both images build from the repository root using the existing API/frontend Dockerfiles. The dashboard's Node server proxies browser `/api/...` requests to the API's **public** Render hostname using HTTPS. This avoids inbound private networking, which is unavailable to Free web services. The API receives the database's private `connectionString` as `POSTGRES_DSN`; its Docker image CMD runs `infra/docker/api-entrypoint.sh`, which bootstraps the database before binding Uvicorn to `$PORT`. Keeping the startup sequence in the image avoids Render Docker Command tokenization differences. If bootstrap fails, the server must not start; `/system/health` returns HTTP 503 if PostgreSQL is down. Dashboard health uses `/` (redirect or HTML), while API health checks PostgreSQL.

The bootstrap registers the existing six Hanoi + six Ho Chi Minh City monitoring anchors. Without operational observations, `/monitoring/points` returns all 12 with `status=missing`, `event_time=null` and `speed_kmh=null`. The demo does not provide verified provider coverage, live traffic, trained forecasts, road geometry or fresh measurements. It does **not** deploy Kafka, Flink, MinIO, Airflow, Redis, MLflow, ingestion/serving workers, or monitoring backends. Nothing in this Blueprint starts polling or seeds synthetic measurements.

## Create the Render Blueprint

1. Merge the reviewed patch to the intended GitHub branch. Validate YAML locally with `python -m pytest -q tests/unit/test_render_blueprint.py` and the Node adapter with `node --test frontend/tests/serve.test.mjs`. Local tests are only configuration and adapter checks, not Render hosting evidence. Before creating resources, also run Render's authoritative workspace-aware check (after installing the Render CLI and authenticating): `render blueprints validate render.yaml`. This check was **not** run when preparing the patch.
2. Sign in to [Render Dashboard](https://dashboard.render.com/) with a workspace that can create services and connect the GitHub repository. In **New → Blueprint**, select `lh6104/INT3229E_BigData__Cognitve-Traffic-Analytics-Platform` and the merged branch. Choose the root `render.yaml` file. Review the displayed **exact three resources** and verify Free plans before approving creation. If the workspace already has a Free PostgreSQL database, Render may reject another.
3. Inspect the creation/build logs. A successful API boot runs the schema/migration/anchor bootstrap and then starts Uvicorn on the Render-assigned `PORT`. The Free dashboard may become available before the API has warmed. The proxy's 120-second timeout gives a Free API time to wake, but startup delays and platform limits can still cause transient 503 responses.
4. Record the actual dashboard HTTPS URL, API URL, Git commit SHA, creation date, Blueprint validation and first-request response. **Do not guess** a service URL from its name; use the URLs shown by Render. Do not add provider API keys or use production data in this demo.

## Post-deployment acceptance (record actual evidence)

From the repository root:

```sh
python scripts/verify_render_demo.py https://<actual-dashboard-hostname>.onrender.com
```

This read-only smoke requires a 200 HTTPS dashboard root, `GET /api/system/health` with `status=healthy` and Postgres `up`, plus the exact 12 point IDs from `GET /api/monitoring/points` (never inventing speed for missing points). Then open the public dashboard in a browser, navigate to monitoring, confirm 12 anchors and explicit unobserved/missing state, and inspect **Network** to confirm calls use dashboard-origin `/api/...` rather than browser-side requests to the API hostname. Capture screenshots or a short browser trace.

Allow the dashboard and API to idle for at least 15 minutes, request the dashboard again, and record first-request behavior and both Render service logs. A cold start may take around a minute or longer. Note all 503s and any failed bootstrap. Store the deployment evidence with its exact commit in the project ledger only **after** those checks pass; until then label it "Blueprint prepared, not hosted".

## Constraints and cleanup

Free Render web services spin down after 15 minutes of inactivity, share a workspace pool of 750 free instance hours/month and may restart. Free Render Postgres has a 1 GB limit, expires after 30 days and provides no backups. Only one Free Postgres database can be active per workspace. The database is disposable; a fresh database may require a fresh Blueprint creation. Restrict external PostgreSQL access (`ipAllowList: []`) while retaining same-region private connectivity. Monitor cost/usage notifications and delete the demo resources after assessment. This is not an HA, monitored or durable deployment.

## Proposed GitHub About description

> Data engineering platform prototype for operator-focused traffic monitoring across 12 configured points in Hanoi and Ho Chi Minh City, with React, FastAPI, PostgreSQL, and replayable event processing.

Setting the repository About description is a separate metadata action and is not performed by the Blueprint.
