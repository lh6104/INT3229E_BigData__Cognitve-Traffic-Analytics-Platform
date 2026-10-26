from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from pathlib import Path

import requests
import structlog
import yaml

from cognitive_traffic.settings import get_settings
from cognitive_traffic.streaming.producers import ContractProducer
from cognitive_traffic.streaming.topics import TRAFFIC_RAW

LOG = structlog.get_logger("traffic-ingestor")
ENDPOINT = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"


def load_points(paths: list[Path]) -> list[dict]:
    points: list[dict] = []
    for path in paths:
        points.extend(yaml.safe_load(path.read_text(encoding="utf-8"))["points"])
    return points


def source_event(point: dict, provider_payload: dict, observed_at: datetime) -> dict:
    flow = provider_payload.get("flowSegmentData", provider_payload)
    return {
        "road_id": point["segment_id"],
        "city": point["city"],
        "event_time": observed_at.isoformat(),
        "ingested_at": datetime.now(UTC).isoformat(),
        "source": "tomtom",
        "source_record_id": f"{point['segment_id']}:{observed_at.isoformat()}",
        "speed_kmh": flow["currentSpeed"],
        "free_flow_speed_kmh": flow["freeFlowSpeed"],
        "confidence": flow.get("confidence", 1.0),
        "provider_payload": provider_payload,
    }


def run_once(session: requests.Session, producer: ContractProducer, points: list[dict], api_key: str) -> int:
    sent = 0
    for point in points:
        try:
            response = session.get(
                ENDPOINT,
                params={"point": f"{point['lat']},{point['lon']}", "unit": "KMPH", "key": api_key},
                timeout=15,
            )
            response.raise_for_status()
            producer.send(TRAFFIC_RAW, source_event(point, response.json(), datetime.now(UTC)))
            sent += 1
        except Exception as exc:
            LOG.warning("source_fetch_failed", road_id=point.get("segment_id"), error=str(exc))
    producer.flush()
    LOG.info("poll_complete", source="tomtom", sent=sent, requested=len(points))
    return sent


def run() -> None:
    api_key = os.environ.get("TOMTOM_API_KEY")
    if not api_key:
        raise RuntimeError("TOMTOM_API_KEY is required")
    paths = [Path(value) for value in os.environ.get(
        "TRAFFIC_POINTS_FILES", "configs/sources.yaml"
    ).split(",")]
    points = load_points(paths)
    producer = ContractProducer(get_settings().kafka_bootstrap_servers)
    interval = int(os.environ.get("TOMTOM_POLL_INTERVAL_SECONDS", "300"))
    with requests.Session() as session:
        while True:
            run_once(session, producer, points, api_key)
            time.sleep(interval)


if __name__ == "__main__":
    run()
