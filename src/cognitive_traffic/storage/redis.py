from __future__ import annotations

import json
from typing import Any


class ForecastCache:
    """Small Redis boundary for latest forecasts; durable history stays in Postgres."""

    def __init__(self, url: str, *, client: Any | None = None) -> None:
        if client is None:
            from redis import Redis

            client = Redis.from_url(url, decode_responses=True)
        self.client = client

    def put(self, road_id: str, horizon_minutes: int, forecast: dict[str, Any], ttl_seconds: int = 900) -> None:
        key = f"forecast:{road_id}:{horizon_minutes}"
        self.client.set(key, json.dumps(forecast, default=str), ex=ttl_seconds)

    def get(self, road_id: str, horizon_minutes: int) -> dict[str, Any] | None:
        value = self.client.get(f"forecast:{road_id}:{horizon_minutes}")
        return json.loads(value) if value else None
