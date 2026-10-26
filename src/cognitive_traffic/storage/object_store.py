"""Partitioned Parquet datasets and lineage manifests in object storage."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from io import BytesIO
from typing import Any, Protocol
from urllib.parse import urlparse

import pyarrow as pa
import pyarrow.parquet as pq


class ObjectStore(Protocol):
    def put_bytes(self, key: str, body: bytes, content_type: str) -> None: ...
    def get_bytes(self, key: str) -> bytes: ...
    def iter_keys(self, prefix: str) -> Iterator[str]: ...
    def delete_keys(self, keys: Iterable[str]) -> None: ...


@dataclass(frozen=True)
class S3Location:
    bucket: str
    prefix: str = ""

    @classmethod
    def parse(cls, uri: str) -> S3Location:
        parsed = urlparse(uri)
        if parsed.scheme != "s3" or not parsed.netloc:
            raise ValueError("object store URI must look like s3://bucket[/prefix]")
        return cls(parsed.netloc, parsed.path.strip("/"))


class S3ObjectStore:
    def __init__(
        self,
        uri: str,
        *,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str = "us-east-1",
        client: object | None = None,
    ) -> None:
        self.location = S3Location.parse(uri)
        if client is None:
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )
        self.client = client

    def _key(self, key: str) -> str:
        clean = key.lstrip("/")
        return f"{self.location.prefix}/{clean}" if self.location.prefix else clean

    def ensure_bucket(self) -> None:
        buckets = {item["Name"] for item in self.client.list_buckets().get("Buckets", [])}
        if self.location.bucket not in buckets:
            self.client.create_bucket(Bucket=self.location.bucket)

    def put_bytes(self, key: str, body: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.location.bucket,
            Key=self._key(key),
            Body=body,
            ContentType=content_type,
        )

    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.location.bucket, Key=self._key(key))
        stream = response["Body"]
        return stream.read() if hasattr(stream, "read") else bytes(stream)

    def iter_keys(self, prefix: str) -> Iterator[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.location.bucket, Prefix=self._key(prefix)):
            for item in page.get("Contents", []):
                key = item["Key"]
                if self.location.prefix:
                    key = key.removeprefix(f"{self.location.prefix}/")
                yield key

    def delete_keys(self, keys: Iterable[str]) -> None:
        objects = [{"Key": self._key(key)} for key in keys]
        for start in range(0, len(objects), 1000):
            batch = objects[start : start + 1000]
            if batch:
                self.client.delete_objects(Bucket=self.location.bucket, Delete={"Objects": batch})


@dataclass(frozen=True)
class DatasetManifest:
    dataset_id: str
    dataset: str
    schema_version: str
    feature_version: str | None
    created_at: str
    source_start: str
    source_end: str
    row_count: int
    objects: tuple[str, ...]


def partition_prefix(layer: str, dataset: str, event_date: date, city: str) -> str:
    if layer not in {"raw", "canonical", "ml", "artifacts"}:
        raise ValueError(f"unsupported lake layer: {layer}")
    safe_city = city.strip().lower().replace(" ", "_")
    return f"{layer}/{dataset}/event_date={event_date.isoformat()}/city={safe_city}"


def parquet_bytes(records: Sequence[dict[str, Any]]) -> bytes:
    if not records:
        raise ValueError("cannot write an empty Parquet object")
    table = pa.Table.from_pylist(list(records))
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="zstd")
    return sink.getvalue().to_pybytes()


def read_parquet(data: bytes) -> pa.Table:
    return pq.read_table(BytesIO(data))


class DatasetWriter:
    def __init__(self, store: ObjectStore) -> None:
        self.store = store

    def write_partition(
        self,
        *,
        layer: str,
        dataset: str,
        records: Sequence[dict[str, Any]],
        event_date: date,
        city: str,
        object_id: str,
    ) -> str:
        prefix = partition_prefix(layer, dataset, event_date, city)
        key = f"{prefix}/part-{object_id}.parquet"
        self.store.put_bytes(key, parquet_bytes(records), "application/vnd.apache.parquet")
        return key

    def write_manifest(
        self,
        *,
        dataset: str,
        schema_version: str,
        feature_version: str | None,
        source_start: datetime,
        source_end: datetime,
        row_count: int,
        objects: Sequence[str],
    ) -> DatasetManifest:
        created_at = datetime.now(UTC).isoformat()
        identity = json.dumps(
            {
                "dataset": dataset,
                "schema_version": schema_version,
                "feature_version": feature_version,
                "source_start": source_start.isoformat(),
                "source_end": source_end.isoformat(),
                "objects": sorted(objects),
            },
            sort_keys=True,
        )
        dataset_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
        manifest = DatasetManifest(
            dataset_id=dataset_id,
            dataset=dataset,
            schema_version=schema_version,
            feature_version=feature_version,
            created_at=created_at,
            source_start=source_start.isoformat(),
            source_end=source_end.isoformat(),
            row_count=row_count,
            objects=tuple(sorted(objects)),
        )
        key = f"ml/manifests/{dataset}/{dataset_id}.json"
        self.store.put_bytes(
            key,
            (json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n").encode(),
            "application/json",
        )
        return manifest


def compact_parquet_objects(
    store: ObjectStore,
    keys: Iterable[str],
    output_key: str,
    *,
    delete_sources: bool = False,
) -> int:
    source_keys = list(keys)
    if not source_keys:
        return 0
    tables = [read_parquet(store.get_bytes(key)) for key in source_keys]
    combined = pa.concat_tables(tables, promote_options="default")
    sink = pa.BufferOutputStream()
    pq.write_table(combined, sink, compression="zstd", row_group_size=100_000)
    store.put_bytes(output_key, sink.getvalue().to_pybytes(), "application/vnd.apache.parquet")
    if delete_sources:
        store.delete_keys(source_keys)
    return combined.num_rows


def compact_partition(prefix: str, output_key: str, *, delete_sources: bool = False) -> int:
    from cognitive_traffic.settings import get_settings

    settings = get_settings()
    store = S3ObjectStore(
        settings.object_store_uri,
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        region=settings.s3_region,
    )
    keys = [key for key in store.iter_keys(prefix) if key.endswith(".parquet") and key != output_key]
    return compact_parquet_objects(store, keys, output_key, delete_sources=delete_sources)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compact Parquet objects in one bounded partition")
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--output-key", required=True)
    parser.add_argument("--delete-sources", action="store_true")
    args = parser.parse_args()
    rows = compact_partition(args.prefix, args.output_key, delete_sources=args.delete_sources)
    print(f"compacted_rows={rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
