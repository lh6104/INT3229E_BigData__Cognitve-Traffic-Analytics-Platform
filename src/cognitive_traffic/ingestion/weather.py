from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from pathlib import Path

import requests
import structlog

from cognitive_traffic.ingestion.traffic import load_points
from cognitive_traffic.monitoring.logging import configure_logging
from cognitive_traffic.settings import get_settings
from cognitive_traffic.streaming.producers import ContractProducer
from cognitive_traffic.streaming.topics import WEATHER_RAW

LOG = structlog.get_logger("weather-ingestor")
ENDPOINT = "https://api.openweathermap.org/data/2.5/weather"


def weather_cells(points: list[dict]) -> list[dict]:
    cells: dict[str, dict] = {}
    for point in points:
        cells.setdefault(
            point["weather_cell_id"],
            {
                "weather_cell_id": point["weather_cell_id"],
                "city": point["city"],
                "lat": point["lat"],
                "lon": point["lon"],
            },
        )
    return list(cells.values())


def source_event(cell: dict, provider_payload: dict, observed_at: datetime) -> dict:
    rain = provider_payload.get("rain", {})
    wind_mps = float(provider_payload.get("wind", {}).get("speed", 0))
    return {
        "weather_cell_id": cell["weather_cell_id"],
        "city": cell["city"],
        "event_time": observed_at.isoformat(),
        "ingested_at": datetime.now(UTC).isoformat(),
        "source": "openweather",
        "source_record_id": f"{cell['weather_cell_id']}:{observed_at.isoformat()}",
        "temperature_c": provider_payload["main"]["temp"],
        "precipitation_mm": rain.get("1h", rain.get("3h", 0)),
        "wind_speed_kmh": wind_mps * 3.6,
        "condition": provider_payload.get("weather", [{}])[0].get("main", "unknown"),
        "provider_payload": provider_payload,
    }


def run_once(session: requests.Session, producer: ContractProducer, cells: list[dict], api_key: str) -> int:
    sent = 0
    for cell in cells:
        try:
            response = session.get(
                ENDPOINT,
                params={"lat": cell["lat"], "lon": cell["lon"], "appid": api_key, "units": "metric"},
                timeout=15,
            )
            response.raise_for_status()
            producer.send(WEATHER_RAW, source_event(cell, response.json(), datetime.now(UTC)))
            sent += 1
        except Exception as exc:
            LOG.warning("source_fetch_failed", weather_cell_id=cell["weather_cell_id"], error_type=type(exc).__name__)
    producer.flush()
    LOG.info("poll_complete", source="openweather", sent=sent, requested=len(cells))
    return sent


def run() -> None:
    configure_logging()
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENWEATHER_API_KEY is required")
    paths = [Path(value) for value in os.environ.get(
        "TRAFFIC_POINTS_FILES", "configs/sources.yaml"
    ).split(",")]
    cells = weather_cells(load_points(paths))
    producer = ContractProducer(get_settings().kafka_bootstrap_servers)
    interval = int(os.environ.get("WEATHER_POLL_INTERVAL_SECONDS", "900"))
    with requests.Session() as session:
        while True:
            run_once(session, producer, cells, api_key)
            time.sleep(interval)


if __name__ == "__main__":
    run()
