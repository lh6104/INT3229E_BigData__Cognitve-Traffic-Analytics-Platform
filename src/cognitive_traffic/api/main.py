from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

from cognitive_traffic.settings import get_settings
from cognitive_traffic.storage.postgres import TrafficRepository

logging.basicConfig(format="%(message)s", level=logging.INFO)
structlog.configure(processors=[structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()])
LOG = structlog.get_logger("traffic-api")
REQUESTS = Counter("traffic_api_requests_total", "HTTP requests", ("method", "path", "status"))
LATENCY = Histogram("traffic_api_request_seconds", "HTTP request latency", ("method", "path"))

app = FastAPI(
    title="Cognitive Traffic API",
    description="Operational reads for traffic state, forecasts, and platform health.",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observe_request(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    LATENCY.labels(request.method, path).observe(time.perf_counter() - started)
    LOG.info("request", method=request.method, path=path, status=response.status_code)
    return response


def repository() -> TrafficRepository:
    return TrafficRepository(get_settings().postgres_dsn)


def query(callable_):
    try:
        return callable_()
    except Exception as exc:
        LOG.warning("dependency_unavailable", dependency="postgres", error=str(exc))
        raise HTTPException(status_code=503, detail="operational store is unavailable") from exc


@app.get("/roads")
def roads(city: str | None = None, repo: TrafficRepository = Depends(repository)):
    return query(lambda: repo.roads(city))


@app.get("/traffic/current")
def current_traffic(city: str | None = None, repo: TrafficRepository = Depends(repository)):
    return query(lambda: repo.current_traffic(city))


@app.get("/traffic/history")
def traffic_history(
    road_id: str,
    limit: int = Query(default=288, ge=1, le=10_000),
    repo: TrafficRepository = Depends(repository),
):
    return query(lambda: repo.traffic_history(road_id, limit))


@app.get("/forecasts")
def forecasts(
    road_id: str | None = None,
    horizon_minutes: int | None = Query(default=None, ge=1),
    repo: TrafficRepository = Depends(repository),
):
    return query(lambda: repo.forecasts(road_id, horizon_minutes))


@app.get("/hotspots")
def hotspots(city: str | None = None, repo: TrafficRepository = Depends(repository)):
    return query(lambda: repo.hotspots(city))


@app.get("/alerts")
def alerts(active_only: bool = True, repo: TrafficRepository = Depends(repository)):
    return query(lambda: repo.alerts(active_only))


@app.get("/models/current")
def current_model(repo: TrafficRepository = Depends(repository)):
    return query(repo.current_model)


@app.get("/models/metrics")
def model_metrics(repo: TrafficRepository = Depends(repository)):
    return query(repo.model_metrics)


@app.get("/system/data-quality")
def data_quality(repo: TrafficRepository = Depends(repository)):
    return query(repo.data_quality)


@app.get("/system/health")
def health(repo: TrafficRepository = Depends(repository)):
    try:
        postgres = repo.ping()
    except Exception as exc:
        LOG.warning("health_check_failed", dependency="postgres", error=str(exc))
        postgres = False
    return {
        "status": "healthy" if postgres else "degraded",
        "service": "traffic-api",
        "dependencies": {"postgres": "up" if postgres else "down"},
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
