from __future__ import annotations

import time
from datetime import UTC, datetime

import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.propagate import extract
from prometheus_client import REGISTRY, Counter, Histogram
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import JSONResponse, Response

from cognitive_traffic.monitoring.logging import configure_logging
from cognitive_traffic.monitoring.tracing import configure_tracing, exemplar
from cognitive_traffic.settings import get_settings
from cognitive_traffic.storage.postgres import TrafficRepository

configure_logging()
configure_tracing()
structlog.configure(logger_factory=structlog.stdlib.LoggerFactory())
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
    status = 500
    with trace.get_tracer(__name__).start_as_current_span(
        "operator.http", context=extract(dict(request.headers)), kind=trace.SpanKind.SERVER,
        record_exception=False, set_status_on_exception=False,
    ) as span:
        try:
            response = await call_next(request)
            status = response.status_code
            ctx = span.get_span_context()
            if ctx.is_valid:
                response.headers["X-Trace-ID"] = f"{ctx.trace_id:032x}"
            return response
        except Exception as exc:
            span.set_status(trace.StatusCode.ERROR)
            LOG.error("request_failed", error_type=type(exc).__name__)
            return JSONResponse({"detail": "internal service error"}, status_code=500)
        finally:
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")
            span.update_name(f"{request.method} {path}")
            span.set_attribute("http.route", path)
            span.set_attribute("http.response.status_code", status)
            if status >= 500:
                span.set_status(trace.StatusCode.ERROR)
            REQUESTS.labels(request.method, path, str(status)).inc(exemplar=exemplar())
            LATENCY.labels(request.method, path).observe(time.perf_counter() - started, exemplar=exemplar())
            LOG.info("request", method=request.method, path=path, status=status)



def repository() -> TrafficRepository:
    return TrafficRepository(get_settings().postgres_dsn)


from cognitive_traffic.api.monitoring import monitoring_router  # noqa: E402

app.include_router(monitoring_router(repository))

def query(callable_):
    try:
        return callable_()
    except Exception as exc:
        LOG.warning("dependency_unavailable", dependency="postgres", error_type=type(exc).__name__)
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
def health(response: Response, repo: TrafficRepository = Depends(repository)):
    try:
        postgres = repo.ping()
    except Exception as exc:
        LOG.warning("health_check_failed", dependency="postgres", error_type=type(exc).__name__)
        postgres = False
    response.status_code = 200 if postgres else 503
    return {
        "status": "healthy" if postgres else "degraded",
        "service": "traffic-api",
        "dependencies": {"postgres": "up" if postgres else "down"},
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
