"""Bootstrap must validate the same approved registry used by serving policy."""
from contextlib import contextmanager
from pathlib import Path

import pytest
import yaml

from cognitive_traffic.storage.bootstrap import bootstrap


@pytest.fixture
def root(tmp_path):
    (tmp_path / "configs").mkdir()
    (tmp_path / "infra/postgres/migrations").mkdir(parents=True)
    (tmp_path / "infra/postgres/schema.sql").write_text("-- fixture schema")
    (tmp_path / "configs/sources.yaml").write_text(Path("configs/sources.yaml").read_text())
    return tmp_path


@pytest.fixture
def sql_calls(monkeypatch):
    calls = []

    class Connection:
        def execute(self, *args):
            calls.append(args)

    class Repository:
        def __init__(self, dsn):
            pass

        @contextmanager
        def connection(self):
            yield Connection()

    monkeypatch.setattr("cognitive_traffic.storage.bootstrap.TrafficRepository", Repository)
    return calls


@pytest.mark.parametrize("field,value", [
    ("segment_id", "UNAPPROVED_POINT"),
    ("city", "wrong_city"),
    ("lat", 999),
    ("lon", -999),
])
def test_invalid_registry_is_rejected_before_database_changes(root, sql_calls, field, value):
    path = root / "configs/sources.yaml"
    config = yaml.safe_load(path.read_text())
    config["points"][0][field] = value
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError):
        bootstrap("fixture-only", root)
    assert sql_calls == []


def test_valid_registry_seeds_original_coordinates_without_inventing_geometry(root, sql_calls):
    bootstrap("fixture-only", root)
    configured = yaml.safe_load((root / "configs/sources.yaml").read_text())["points"]
    inserts = [call for call in sql_calls if call[0].lstrip().startswith("INSERT INTO roads")]
    assert len(inserts) == 12
    expected = {
        (point["segment_id"], point["city"], point["segment_id"], point["lat"], point["lon"])
        for point in configured
    }
    assert {call[1] for call in inserts} == expected
    assert all("geometry" not in call[0] for call in inserts)
