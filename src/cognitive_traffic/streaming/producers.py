"""Kafka producer that enforces contract serialization and key policy."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from cognitive_traffic.streaming.topics import TopicSpec


class ContractProducer:
    def __init__(self, bootstrap_servers: str, *, producer: Any | None = None) -> None:
        if producer is None:
            from confluent_kafka import Producer

            producer = Producer(
                {
                    "bootstrap.servers": bootstrap_servers,
                    "enable.idempotence": True,
                    "acks": "all",
                    "compression.type": "zstd",
                }
            )
        self._producer = producer

    def send(self, topic: TopicSpec, event: BaseModel | dict[str, Any]) -> None:
        payload = event.model_dump(mode="json") if isinstance(event, BaseModel) else event
        key = payload.get(topic.key_field)
        if not key:
            raise ValueError(f"{topic.name} requires partition key field {topic.key_field}")
        self._producer.produce(
            topic.name,
            key=str(key).encode("utf-8"),
            value=json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
        )
        self._producer.poll(0)

    def flush(self, timeout: float = 10) -> None:
        remaining = self._producer.flush(timeout)
        if remaining:
            raise TimeoutError(f"{remaining} Kafka messages were not delivered")
