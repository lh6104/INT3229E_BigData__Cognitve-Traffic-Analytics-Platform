"""Load and enforce the bounded monitoring and dataset registry policy."""

from collections.abc import Mapping
from pathlib import Path

import yaml

from cognitive_traffic.contracts.registry import DatasetProfile, MonitoringPoint

APPROVED_POINT_CITIES = {
    "HN_HK_001": "hanoi",
    "HN_BD_001": "hanoi",
    "HN_CG_001": "hanoi",
    "HN_TX_001": "hanoi",
    "HN_RR3_001": "hanoi",
    "HN_VNG_001": "hanoi",
    "HCMC_D1_001": "hcmc",
    "HCMC_D3_001": "hcmc",
    "HCMC_BT_001": "hcmc",
    "HCMC_TD_001": "hcmc",
    "HCMC_Q7_001": "hcmc",
    "HCMC_CL_001": "hcmc",
}
APPROVED_POINT_IDS = frozenset(APPROVED_POINT_CITIES)


def _read_yaml_mapping(path: Path, *, expected_key: str) -> Mapping[str, object]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping) or expected_key not in raw:
        raise ValueError(f"configuration must be a mapping containing {expected_key!r}")
    if not isinstance(raw[expected_key], list):
        raise ValueError(f"configuration field {expected_key!r} must be a list")
    return raw


def load_monitoring_points(path: Path) -> tuple[MonitoringPoint, ...]:
    raw = _read_yaml_mapping(path, expected_key="points")
    points = tuple(MonitoringPoint.model_validate(row) for row in raw["points"])
    ids = [point.point_id for point in points]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate monitoring point")
    if set(ids) != APPROVED_POINT_IDS:
        raise ValueError("registry must contain exactly the 12 approved points")
    if any(point.city != APPROVED_POINT_CITIES[point.point_id] for point in points):
        raise ValueError("point city differs from approved registry")
    return tuple(sorted(points, key=lambda point: point.point_id))


def load_dataset_profiles(path: Path) -> dict[str, DatasetProfile]:
    raw = _read_yaml_mapping(path, expected_key="profiles")
    if raw.get("schema_version") != "1":
        raise ValueError("unsupported profile schema_version")
    profiles = [DatasetProfile.model_validate(row) for row in raw["profiles"]]
    ids = [profile.dataset_id for profile in profiles]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate dataset_id")
    return {profile.dataset_id: profile for profile in sorted(profiles, key=lambda item: item.dataset_id)}


def may_serve_current(
    profile: DatasetProfile,
    *,
    mode: str,
    point_id: str,
    points: tuple[MonitoringPoint, ...],
) -> bool:
    if mode not in {"live", "replay", "reprocess"}:
        raise ValueError("unsupported execution mode")
    return (
        profile.dataset_id == "vn-mvp-12"
        and profile.purpose == "operational"
        and profile.measurement == "speed"
        and profile.unit == "km/h"
        and mode == "live"
        and point_id in {point.point_id for point in points}
    )
