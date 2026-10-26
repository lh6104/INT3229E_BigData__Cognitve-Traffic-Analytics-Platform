from datetime import date

from cognitive_traffic.storage.object_store import (
    DatasetWriter,
    S3Location,
    compact_parquet_objects,
    read_parquet,
)


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, body: bytes, content_type: str) -> None:
        self.objects[key] = body

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def iter_keys(self, prefix: str):
        yield from (key for key in sorted(self.objects) if key.startswith(prefix))

    def delete_keys(self, keys):
        for key in keys:
            del self.objects[key]


def test_s3_uri_is_required() -> None:
    assert S3Location.parse("s3://cognitive-traffic/root").bucket == "cognitive-traffic"


def test_partitioning_uses_date_and_city_not_road() -> None:
    store = MemoryStore()
    writer = DatasetWriter(store)
    key = writer.write_partition(
        layer="canonical",
        dataset="traffic",
        records=[{"road_id": "HN-001", "speed_kmh": 30.0}],
        event_date=date(2026, 8, 12),
        city="Ha Noi",
        object_id="a",
    )
    assert key == "canonical/traffic/event_date=2026-08-12/city=ha_noi/part-a.parquet"
    assert "road_id=" not in key


def test_compaction_combines_small_objects() -> None:
    store = MemoryStore()
    writer = DatasetWriter(store)
    keys = [
        writer.write_partition(
            layer="canonical",
            dataset="traffic",
            records=[{"road_id": f"HN-00{index}", "speed_kmh": 30.0}],
            event_date=date(2026, 8, 12),
            city="hanoi",
            object_id=str(index),
        )
        for index in (1, 2)
    ]
    count = compact_parquet_objects(store, keys, "canonical/traffic/compacted.parquet", delete_sources=True)
    assert count == 2
    assert read_parquet(store.objects["canonical/traffic/compacted.parquet"]).num_rows == 2
    assert not any(key in store.objects for key in keys)
