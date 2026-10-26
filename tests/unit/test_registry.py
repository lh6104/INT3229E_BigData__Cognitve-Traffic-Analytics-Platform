from collections import Counter
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from cognitive_traffic.contracts.registry import DatasetProfile
from cognitive_traffic.monitoring.registry import load_dataset_profiles, load_monitoring_points, may_serve_current

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "configs/sources.yaml"
DATASETS = ROOT / "configs/datasets.yaml"


def read_sources(tmp_path: Path) -> tuple[dict, Path]:
    data = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    path = tmp_path / "sources.yaml"
    return data, path


def test_configured_registry_has_fixed_scope_and_preserves_configured_coordinates() -> None:
    points = load_monitoring_points(SOURCES)
    source_rows = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))["points"]
    expected = {row["segment_id"]: row for row in source_rows}

    assert len(points) == 12
    assert Counter(point.city for point in points) == {"hanoi": 6, "hcmc": 6}
    assert {point.point_id for point in points} == set(expected)
    assert all(
        (point.lat, point.lon, point.weather_cell_id)
        == (
            expected[point.point_id]["lat"],
            expected[point.point_id]["lon"],
            expected[point.point_id]["weather_cell_id"],
        )
        for point in points
    )
    assert points == tuple(sorted(points, key=lambda point: point.point_id))


def test_duplicate_point_is_rejected_before_scope_validation(tmp_path: Path) -> None:
    data, path = read_sources(tmp_path)
    data["points"].append(data["points"][0])
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate"):
        load_monitoring_points(path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda rows: rows.pop(), "exactly the 12 approved points"),
        (
            lambda rows: rows.append(
                {"city": "hanoi", "segment_id": "HN_NEW_001", "weather_cell_id": "W", "lat": 21, "lon": 105}
            ),
            "exactly the 12 approved points",
        ),
        (lambda rows: rows[0].update(city="hcmc"), "city differs"),
        (lambda rows: rows[0].update(lat=91), "lat"),
        (lambda rows: rows[0].update(lon=181), "lon"),
        (lambda rows: rows[0].update(extra="unsupported"), "extra"),
    ],
)
def test_invalid_monitoring_registry_is_rejected(tmp_path: Path, mutation, message: str) -> None:
    data, path = read_sources(tmp_path)
    mutation(data["points"])
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises((ValueError, ValidationError), match=message):
        load_monitoring_points(path)


def test_dataset_profiles_preserve_measurement_units_and_unverified_status() -> None:
    profiles = load_dataset_profiles(DATASETS)

    assert profiles["vn-mvp-12"].unit == "km/h"
    assert profiles["metr-la"].unit == "mph"
    assert profiles["ua-detrac"].measurement == "video"
    assert profiles["ua-detrac"].unit == "frame"
    assert profiles["largest"].measurement == "flow"
    assert profiles["largest"].unit == "source_units_unverified"
    assert {profile.acquisition_status for profile in profiles.values()} == {"configured_unverified", "not_acquired"}
    assert {profile.rights_status for profile in profiles.values()} == {"unverified"}


def test_measurement_and_unit_must_be_compatible() -> None:
    profile = DatasetProfile(
        dataset_id="largest",
        profile_version="1",
        purpose="benchmark",
        measurement="flow",
        unit="source_units_unverified",
        source_reference="https://github.com/liuxu77/LargeST",
        acquisition_status="not_acquired",
        rights_status="unverified",
    )

    with pytest.raises(ValidationError, match="measurement/unit"):
        DatasetProfile(**{**profile.model_dump(), "unit": "km/h"})


@pytest.mark.parametrize(
    "field,value",
    [("purpose", "unknown"), ("acquisition_status", "downloaded"), ("rights_status", "verified")],
)
def test_dataset_profile_rejects_unapproved_status_values(field: str, value: str) -> None:
    payload = {
        "dataset_id": "test",
        "profile_version": "1",
        "purpose": "benchmark",
        "measurement": "speed",
        "unit": "mph",
        "source_reference": "https://example.org/dataset",
        "acquisition_status": "not_acquired",
        "rights_status": "unverified",
    }
    payload[field] = value
    with pytest.raises(ValidationError):
        DatasetProfile(**payload)


def test_profile_loader_rejects_duplicate_ids_and_invalid_schema(tmp_path: Path) -> None:
    data = yaml.safe_load(DATASETS.read_text(encoding="utf-8"))
    path = tmp_path / "datasets.yaml"
    data["profiles"].append(data["profiles"][0])
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate dataset_id"):
        load_dataset_profiles(path)

    data["schema_version"] = "2"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        load_dataset_profiles(path)


@pytest.mark.parametrize(
    ("dataset_id", "mode", "point_id", "expected"),
    [
        ("vn-mvp-12", "live", "HN_HK_001", True),
        ("vn-mvp-12", "replay", "HN_HK_001", False),
        ("vn-mvp-12", "reprocess", "HN_HK_001", False),
        ("vn-mvp-12", "live", "unknown", False),
        ("metr-la", "live", "HN_HK_001", False),
        ("largest", "live", "HN_HK_001", False),
    ],
)
def test_current_serving_policy(dataset_id: str, mode: str, point_id: str, expected: bool) -> None:
    points = load_monitoring_points(SOURCES)
    profiles = load_dataset_profiles(DATASETS)
    assert may_serve_current(profiles[dataset_id], mode=mode, point_id=point_id, points=points) is expected


def test_current_serving_policy_rejects_unknown_mode_and_spoofed_profile() -> None:
    points = load_monitoring_points(SOURCES)
    profile = load_dataset_profiles(DATASETS)["vn-mvp-12"]

    with pytest.raises(ValueError, match="execution mode"):
        may_serve_current(profile, mode="shadow", point_id="HN_HK_001", points=points)
    unit_mismatch = DatasetProfile(**{**profile.model_dump(), "unit": "mph"})
    assert not may_serve_current(unit_mismatch, mode="live", point_id="HN_HK_001", points=points)
