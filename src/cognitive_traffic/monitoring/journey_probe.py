"""Probe the actual operator read path; an empty measurement list is legitimate."""
from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime
from urllib.request import urlopen

from prometheus_client import Gauge, start_http_server


def _number(value, lower, upper):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and lower <= value <= upper)


def semantic_success(health, traffic, points=None):
    from cognitive_traffic.monitoring.registry import APPROVED_POINT_CITIES
    if not (isinstance(health, dict) and health.get('status') == 'healthy'
            and health.get('dependencies', {}).get('postgres') == 'up' and isinstance(traffic, list)
            and all(isinstance(row, dict) and 'road_id' in row for row in traffic)
            and isinstance(points, list) and len(points) == 12):
        return False
    seen = set()
    measurements = {'event_time', 'speed_kmh', 'free_flow_speed_kmh', 'confidence', 'source', 'dataset_id', 'mode'}
    required = measurements | {'road_id', 'city', 'name', 'category', 'latitude',
                               'longitude', 'coordinate_kind', 'status'}
    for row in points:
        if not isinstance(row, dict) or not required.issubset(row):
            return False
        identity = row['road_id']
        if not isinstance(identity, str) or identity in seen or APPROVED_POINT_CITIES.get(identity) != row['city']:
            return False
        seen.add(identity)
        if (not _number(row['latitude'], -90, 90) or not _number(row['longitude'], -180, 180)
                or row['coordinate_kind'] != 'configured_anchor'
                or row['status'] not in {'missing', 'stale', 'live'}
                or not all(isinstance(row[k], str) and row[k] for k in ('name', 'category'))):
            return False
        if row['status'] == 'missing':
            if any(row[k] is not None for k in measurements):
                return False
        else:
            if (not _number(row['speed_kmh'], 0, 300) or not _number(row['free_flow_speed_kmh'], 0, 300)
                    or not _number(row['confidence'], 0, 1) or row['dataset_id'] != 'vn-mvp-12'
                    or row['mode'] != 'operational' or not isinstance(row['source'], str) or not row['source']):
                return False
            try:
                if datetime.fromisoformat(row['event_time']).tzinfo is None:
                    return False
            except (TypeError, ValueError):
                return False
    return seen == set(APPROVED_POINT_CITIES)


def probe(base_url):
    try:
        with urlopen(base_url.rstrip('/') + '/system/health', timeout=3) as response:
            health = json.load(response)
        with urlopen(base_url.rstrip('/') + '/traffic/current', timeout=3) as response:
            traffic = json.load(response)
        with urlopen(base_url.rstrip('/') + '/monitoring/points', timeout=3) as response:
            points = json.load(response)
        return semantic_success(health, traffic, points)
    except Exception:
        return False


def main():
    success = Gauge('traffic_operator_journey_success', 'Semantic health and current traffic read success')
    checked = Gauge('traffic_operator_journey_checked_timestamp_seconds', 'Last completed journey probe')
    start_http_server(int(os.getenv('PROBE_PORT', '9101')))
    while True:
        success.set(int(probe(os.getenv('API_BASE_URL', 'http://api:8000'))))
        checked.set(time.time())
        time.sleep(5)


if __name__ == '__main__':
    main()
