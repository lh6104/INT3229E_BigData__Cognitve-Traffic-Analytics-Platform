from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from cognitive_traffic.settings import get_settings
from cognitive_traffic.storage.object_store import S3ObjectStore, read_parquet
from cognitive_traffic.streaming.producers import ContractProducer
from cognitive_traffic.streaming.topics import NEWS_RAW, TRAFFIC_RAW, WEATHER_RAW, TopicSpec

DATASET_TOPICS: dict[str, TopicSpec] = {
    "traffic": TRAFFIC_RAW,
    "weather": WEATHER_RAW,
    "news": NEWS_RAW,
}


def replay_payload(payload: dict) -> dict:
    """An archived operational source is no longer a live delivery on replay."""
    return {**payload, "mode": "replay"}


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("replay timestamps must include a timezone")
    return parsed.astimezone(UTC)


def replay(*, start: datetime, end: datetime, dataset: str | None = None) -> int:
    if end <= start:
        raise ValueError("END must be later than START")
    settings = get_settings()
    store = S3ObjectStore(
        settings.object_store_uri,
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        region=settings.s3_region,
    )
    producer = ContractProducer(settings.kafka_bootstrap_servers)
    datasets = [dataset] if dataset else list(DATASET_TOPICS)
    sent = 0
    for name in datasets:
        topic = DATASET_TOPICS[name]
        for key in store.iter_keys(f"raw/{name}/"):
            if not key.endswith(".parquet"):
                continue
            for record in read_parquet(store.get_bytes(key)).to_pylist():
                event_time = record["event_time"]
                if event_time.tzinfo is None:
                    event_time = event_time.replace(tzinfo=UTC)
                if start <= event_time < end:
                    payload = json.loads(record["payload_json"])
                    producer.send(topic, replay_payload(payload))
                    sent += 1
    producer.flush()
    return sent


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay archived source events through Kafka")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--dataset", choices=sorted(DATASET_TOPICS))
    args = parser.parse_args()
    count = replay(start=parse_time(args.start), end=parse_time(args.end), dataset=args.dataset)
    print(f"replayed_events={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
