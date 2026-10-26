"""Small Prometheus surface for long-running stream workers."""

from __future__ import annotations

from dataclasses import dataclass

from prometheus_client import CollectorRegistry, Counter, start_http_server


@dataclass(frozen=True)
class WorkerMetrics:
    events_received: Counter
    events_invalid: Counter
    normalizer_processed: Counter | None = None
    archive_objects_written: Counter | None = None


def start_worker_metrics(*, service: str, port: int, topics: tuple[str, ...]) -> WorkerMetrics:
    registry = CollectorRegistry()
    events_received = Counter(
        "traffic_events_received_total",
        "Kafka events received by a stream worker.",
        ("topic",),
        registry=registry,
    )
    events_invalid = Counter(
        "traffic_events_invalid_total",
        "Kafka events rejected by a stream worker.",
        ("topic",),
        registry=registry,
    )
    for topic in topics:
        events_received.labels(topic).inc(0)
        events_invalid.labels(topic).inc(0)

    normalizer_processed = None
    archive_objects_written = None
    if service == "normalizer":
        normalizer_processed = Counter(
            "normalizer_events_processed_total",
            "Events handled by the canonical normalizer.",
            ("outcome",),
            registry=registry,
        )
        normalizer_processed.labels("accepted").inc(0)
        normalizer_processed.labels("invalid").inc(0)
    elif service == "raw-archive":
        archive_objects_written = Counter(
            "archive_objects_written_total",
            "Parquet objects written by the raw archive worker.",
            registry=registry,
        )
        archive_objects_written.inc(0)
    else:
        raise ValueError(f"unsupported metrics service: {service}")

    start_http_server(port, registry=registry)
    return WorkerMetrics(
        events_received=events_received,
        events_invalid=events_invalid,
        normalizer_processed=normalizer_processed,
        archive_objects_written=archive_objects_written,
    )
