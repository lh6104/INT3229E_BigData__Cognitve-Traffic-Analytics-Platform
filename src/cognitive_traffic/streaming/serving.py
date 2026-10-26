"""At-least-once Kafka delivery with transactional, idempotent PostgreSQL writes."""
from __future__ import annotations

import os

import structlog

from cognitive_traffic.contracts.traffic import TrafficObservation
from cognitive_traffic.settings import get_settings
from cognitive_traffic.storage.postgres import TrafficRepository
from cognitive_traffic.streaming.topics import TRAFFIC_OBSERVATIONS

LOG = structlog.get_logger('traffic-serving')


def run() -> None:
    from confluent_kafka import Consumer, KafkaException

    settings = get_settings()
    repository = TrafficRepository(settings.postgres_dsn)
    consumer = Consumer({
        'bootstrap.servers': settings.kafka_bootstrap_servers,
        'group.id': os.environ.get('SERVING_CONSUMER_GROUP', 'traffic-serving-v1'),
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': False,
        'enable.auto.offset.store': False,
    })
    consumer.subscribe([TRAFFIC_OBSERVATIONS.name])
    try:
        while True:
            message = consumer.poll(1)
            if message is None:
                continue
            if message.error():
                raise KafkaException(message.error())
            try:
                event = TrafficObservation.model_validate_json(message.value())
                status = repository.store_observation(event)
            except ValueError:
                # Deliberate policy/contract rejection, never reinterpret as a live
                # observation. Offset is sufficient to locate the retained record.
                status = 'rejected'
            # DB/network exceptions escape: do not commit and lose an observation.
            LOG.info('serving_delivery', status=status, topic=message.topic(),
                     partition=message.partition(), offset=message.offset())
            consumer.commit(message=message, asynchronous=False)
    finally:
        consumer.close()


if __name__ == '__main__':
    run()
