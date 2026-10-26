from __future__ import annotations

import hashlib
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import feedparser
import yaml

from cognitive_traffic.monitoring.logging import configure_logging
from cognitive_traffic.settings import get_settings
from cognitive_traffic.streaming.producers import ContractProducer
from cognitive_traffic.streaming.topics import NEWS_RAW


def load_feeds(path: Path = Path("configs/sources.yaml")) -> list[dict]:
    sources = yaml.safe_load(path.read_text(encoding="utf-8"))["sources"]
    return [source for source in sources if source.get("enabled", True) and source["type"] == "rss"]


def source_event(source: dict, entry: dict) -> dict:
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    event_time = (
        datetime(*published[:6], tzinfo=UTC)
        if published
        else datetime.now(UTC)
    )
    url = str(entry.get("link", ""))
    record_id = str(entry.get("id") or url or entry.get("title", ""))
    return {
        "event_time": event_time.isoformat(),
        "ingested_at": datetime.now(UTC).isoformat(),
        "source": source["name"],
        "source_record_id": hashlib.sha256(record_id.encode("utf-8")).hexdigest(),
        "road_id": "unmatched",
        "city": str(source.get("city_hint") or "unknown").lower(),
        "event_type": "other",
        "severity": 0,
        "confidence": 0.0,
        "title": str(entry.get("title", "")),
        "url": url,
        "summary": str(entry.get("summary", "")),
    }


def run_once(producer: ContractProducer, feeds: list[dict]) -> int:
    sent = 0
    for source in feeds:
        parsed = feedparser.parse(source["url"])
        for entry in parsed.entries:
            producer.send(NEWS_RAW, source_event(source, entry))
            sent += 1
    producer.flush()
    return sent


def run() -> None:
    configure_logging()
    feeds = load_feeds(Path(os.environ.get("SOURCES_FILE", "configs/sources.yaml")))
    producer = ContractProducer(get_settings().kafka_bootstrap_servers)
    interval = int(os.environ.get("NEWS_POLL_INTERVAL_SECONDS", "600"))
    while True:
        run_once(producer, feeds)
        time.sleep(interval)


if __name__ == "__main__":
    run()
