"""Deterministic event-time reference processor used by tests and replay.

The PyFlink job uses managed state in production. Keeping this state machine
framework-independent makes late-event and replay semantics directly testable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from cognitive_traffic.contracts.events import DeadLetterEvent, RoadEvent, RoadEventType
from cognitive_traffic.contracts.forecasts import TrafficFeatures
from cognitive_traffic.contracts.traffic import TrafficObservation
from cognitive_traffic.contracts.weather import WeatherObservation
from cognitive_traffic.forecasting.features import PointInTimeFeatureBuilder
from cognitive_traffic.settings import get_settings
from cognitive_traffic.storage.object_store import DatasetWriter, S3ObjectStore
from cognitive_traffic.streaming.producers import ContractProducer
from cognitive_traffic.streaming.topics import (
    DEAD_LETTER,
    NEWS_RAW,
    ROAD_EVENTS,
    TRAFFIC_OBSERVATIONS,
    TRAFFIC_RAW,
    WEATHER_OBSERVATIONS,
    WEATHER_RAW,
)

ContractModel = TypeVar("ContractModel", bound=BaseModel)


@dataclass(frozen=True)
class ProcessingResult:
    status: str
    feature: TrafficFeatures | None = None
    reason: str | None = None


class EventTimeFeatureProcessor:
    def __init__(self, *, watermark_delay: timedelta = timedelta(minutes=2), feature_version: str = "1") -> None:
        if watermark_delay < timedelta(0):
            raise ValueError("watermark delay cannot be negative")
        self.watermark_delay = watermark_delay
        self.builder = PointInTimeFeatureBuilder(feature_version)
        self.max_event_time: datetime | None = None
        self.history: dict[str, list[TrafficObservation]] = {}
        self.seen: set[str] = set()

    @property
    def watermark(self) -> datetime | None:
        return self.max_event_time - self.watermark_delay if self.max_event_time else None

    def process(self, event: TrafficObservation) -> ProcessingResult:
        if event.event_id in self.seen:
            return ProcessingResult("duplicate", reason="event_id already processed")
        self.seen.add(event.event_id)
        event_time = event.event_time.astimezone(UTC)
        previous_watermark = self.watermark
        if previous_watermark is not None and event_time < previous_watermark:
            return ProcessingResult("late", reason=f"event_time precedes watermark {previous_watermark.isoformat()}")
        if self.max_event_time is None or event_time > self.max_event_time:
            self.max_event_time = event_time
        road_history = self.history.setdefault(event.road_id, [])
        road_history.append(event)
        road_history.sort(key=lambda item: (item.event_time, item.event_id))
        prediction_time = max(event_time, event.available_at.astimezone(UTC))
        cutoff = prediction_time - timedelta(minutes=60)
        self.history[event.road_id] = [item for item in road_history if item.event_time >= cutoff]
        feature = self.builder.build(
            road_id=event.road_id,
            city=event.city,
            prediction_time=prediction_time,
            traffic=self.history[event.road_id],
        )
        return ProcessingResult("accepted", feature=feature)


def source_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("source event_time is required")
    if parsed.tzinfo is None:
        raise ValueError("source event_time must include a timezone")
    return parsed.astimezone(UTC)


def normalize_traffic(payload: dict[str, Any]) -> TrafficObservation:
    event_time = source_timestamp(payload.get("event_time") or payload.get("timestamp"))
    ingested_at = source_timestamp(payload.get("ingested_at") or datetime.now(UTC))
    return TrafficObservation.create(
        dataset_id=str(payload.get("dataset_id", "unspecified")),
        mode=str(payload.get("mode", "unspecified")),
        road_id=str(payload.get("road_id") or payload.get("segment_id") or ""),
        city=str(payload["city"]).lower(),
        event_time=event_time,
        ingested_at=ingested_at,
        available_at=ingested_at,
        speed_kmh=float(payload.get("speed_kmh", payload.get("currentSpeed"))),
        free_flow_speed_kmh=float(payload.get("free_flow_speed_kmh", payload.get("freeFlowSpeed"))),
        confidence=float(payload.get("confidence", 1.0)),
        source=str(payload.get("source", "unknown")),
        source_record_id=str(payload.get("source_record_id", payload.get("id", ""))),
    )


def normalize_weather(payload: dict[str, Any]) -> WeatherObservation:
    event_time = source_timestamp(payload.get("event_time") or payload.get("timestamp"))
    ingested_at = source_timestamp(payload.get("ingested_at") or datetime.now(UTC))
    return WeatherObservation.create(
        weather_cell_id=str(payload.get("weather_cell_id") or payload.get("cell_id") or payload["city"]),
        city=str(payload["city"]).lower(),
        event_time=event_time,
        ingested_at=ingested_at,
        available_at=ingested_at,
        temperature_c=float(payload.get("temperature_c", payload.get("temperature"))),
        precipitation_mm=float(payload.get("precipitation_mm", payload.get("rain_mm", 0))),
        wind_speed_kmh=float(payload.get("wind_speed_kmh", payload.get("wind_speed", 0))),
        condition=str(payload.get("condition", "unknown")),
        source=str(payload.get("source", "unknown")),
        source_record_id=str(payload.get("source_record_id", payload.get("id", ""))),
    )


def normalize_road_event(payload: dict[str, Any]) -> RoadEvent:
    event_time = source_timestamp(payload.get("event_time") or payload.get("published_at"))
    ingested_at = source_timestamp(
        payload.get("ingested_at") or payload.get("crawled_at") or datetime.now(UTC)
    )
    return RoadEvent.create(
        road_id=str(payload["road_id"]),
        city=str(payload["city"]).lower(),
        event_type=RoadEventType(str(payload.get("event_type", "other"))),
        severity=int(payload.get("severity", 0)),
        confidence=float(payload.get("confidence", payload.get("event_confidence", 0))),
        event_time=event_time,
        ingested_at=ingested_at,
        available_at=ingested_at,
        source=str(payload.get("source", "rss")),
        source_record_id=str(payload.get("source_record_id", payload.get("external_id", ""))),
    )


def dead_letter_for(*, original_topic: str, payload: dict[str, Any], error: Exception) -> DeadLetterEvent:
    digest = hashlib.sha256(
        (original_topic + json.dumps(payload, sort_keys=True, default=str)).encode("utf-8")
    ).hexdigest()
    return DeadLetterEvent(
        original_topic=original_topic,
        event_id=str(payload.get("event_id") or digest),
        failure_reason=str(error),
        failed_at=datetime.now(UTC),
        payload=payload,
    )


def validate_or_dead_letter(
    model: type[ContractModel], *, original_topic: str, payload: dict[str, Any]
) -> tuple[ContractModel | None, DeadLetterEvent | None]:
    try:
        return model.model_validate(payload), None
    except ValidationError as exc:
        return None, dead_letter_for(original_topic=original_topic, payload=payload, error=exc)


NORMALIZATION_ROUTES = {
    TRAFFIC_RAW.name: (normalize_traffic, TRAFFIC_OBSERVATIONS),
    WEATHER_RAW.name: (normalize_weather, WEATHER_OBSERVATIONS),
    NEWS_RAW.name: (normalize_road_event, ROAD_EVENTS),
}


def run_normalizer() -> None:
    from confluent_kafka import Consumer

    from cognitive_traffic.monitoring.prometheus import start_worker_metrics

    settings = get_settings()
    metrics = start_worker_metrics(
        service="normalizer",
        port=int(os.environ.get("METRICS_PORT", "9101")),
        topics=tuple(NORMALIZATION_ROUTES),
    )
    producer = ContractProducer(settings.kafka_bootstrap_servers)
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": "canonical-normalizer-v1",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe(list(NORMALIZATION_ROUTES))
    try:
        while True:
            message = consumer.poll(1)
            if message is None or message.error() is not None:
                continue
            metrics.events_received.labels(message.topic()).inc()
            payload = json.loads(message.value().decode("utf-8"))
            normalizer, output_topic = NORMALIZATION_ROUTES[message.topic()]
            try:
                event = normalizer(payload)
            except Exception as exc:
                metrics.events_invalid.labels(message.topic()).inc()
                metrics.normalizer_processed.labels("invalid").inc()
                producer.send(
                    DEAD_LETTER,
                    dead_letter_for(original_topic=message.topic(), payload=payload, error=exc),
                )
            else:
                metrics.normalizer_processed.labels("accepted").inc()
                producer.send(output_topic, event)
            producer.flush()
            consumer.commit(message=message, asynchronous=False)
    finally:
        consumer.close()


TOPIC_DATASETS = {
    TRAFFIC_RAW.name: "traffic",
    WEATHER_RAW.name: "weather",
    NEWS_RAW.name: "news",
}


def archive_batch(messages: list[Any], writer: DatasetWriter) -> list[str]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for message in messages:
        payload = json.loads(message.value().decode("utf-8"))
        event_time = source_timestamp(payload["event_time"])
        partition = (
            TOPIC_DATASETS[message.topic()],
            event_time.date().isoformat(),
            str(payload.get("city", "unknown")),
        )
        grouped[partition].append(
            {
                "topic": message.topic(),
                "partition": message.partition(),
                "offset": message.offset(),
                "kafka_timestamp_ms": message.timestamp()[1],
                "event_time": event_time,
                "ingested_at": datetime.now(UTC),
                "event_id": payload.get("event_id"),
                "schema_version": payload.get("schema_version", "unknown"),
                "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            }
        )
    keys: list[str] = []
    for (dataset, day, city), records in grouped.items():
        keys.append(
            writer.write_partition(
                layer="raw",
                dataset=dataset,
                records=records,
                event_date=datetime.fromisoformat(day).date(),
                city=city,
                object_id=uuid.uuid4().hex,
            )
        )
    return keys


def run_archive() -> None:
    from confluent_kafka import Consumer

    from cognitive_traffic.monitoring.prometheus import start_worker_metrics

    settings = get_settings()
    metrics = start_worker_metrics(
        service="raw-archive",
        port=int(os.environ.get("METRICS_PORT", "9102")),
        topics=tuple(TOPIC_DATASETS),
    )
    store = S3ObjectStore(
        settings.object_store_uri,
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        region=settings.s3_region,
    )
    store.ensure_bucket()
    writer = DatasetWriter(store)
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": "raw-archive-v1",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe(list(TOPIC_DATASETS))
    try:
        while True:
            messages = consumer.consume(num_messages=500, timeout=5)
            valid = [message for message in messages if message is not None and message.error() is None]
            if valid:
                for message in valid:
                    metrics.events_received.labels(message.topic()).inc()
                keys = archive_batch(valid, writer)
                metrics.archive_objects_written.inc(len(keys))
                consumer.commit(asynchronous=False)
    finally:
        consumer.close()


def run_flink_features(bootstrap_servers: str, checkpoint_uri: str) -> None:
    """Run the production event-time rolling feature job in PyFlink."""
    from pyflink.datastream import StreamExecutionEnvironment
    from pyflink.table import EnvironmentSettings, StreamTableEnvironment

    environment = StreamExecutionEnvironment.get_execution_environment()
    environment.set_parallelism(6)
    environment.enable_checkpointing(30_000)
    environment.get_checkpoint_config().set_checkpoint_storage(checkpoint_uri)
    tables = StreamTableEnvironment.create(
        environment,
        environment_settings=EnvironmentSettings.in_streaming_mode(),
    )
    tables.get_config().set("table.exec.source.idle-timeout", "5 s")
    tables.execute_sql(
        """
        CREATE TEMPORARY SYSTEM FUNCTION mean_15m AS
          'org.cognitivetraffic.flink.RollingEventTimeMeans$Mean15m'
        """
    )
    tables.execute_sql(
        """
        CREATE TEMPORARY SYSTEM FUNCTION mean_30m AS
          'org.cognitivetraffic.flink.RollingEventTimeMeans$Mean30m'
        """
    )
    tables.execute_sql(
        f"""
        CREATE TABLE traffic_observations (
          event_id STRING, event_time TIMESTAMP_LTZ(3), ingested_at TIMESTAMP_LTZ(3),
          source STRING, source_record_id STRING, schema_version STRING,
          road_id STRING, city STRING, available_at TIMESTAMP_LTZ(3),
          speed_kmh DOUBLE, free_flow_speed_kmh DOUBLE, confidence DOUBLE,
          WATERMARK FOR event_time AS event_time - INTERVAL '6' MINUTE
        ) WITH (
          'connector' = 'kafka', 'topic' = 'traffic.observation.v1',
          'properties.bootstrap.servers' = '{bootstrap_servers}',
          'properties.group.id' = 'traffic-features-v1',
          'scan.startup.mode' = 'group-offsets', 'format' = 'json',
          'json.fail-on-missing-field' = 'true'
        )
        """
    )
    tables.execute_sql(
        f"""
        CREATE TABLE traffic_features (
          event_id STRING, event_time TIMESTAMP_LTZ(3), ingested_at TIMESTAMP_LTZ(3),
          source STRING, source_record_id STRING, schema_version STRING,
          road_id STRING, city STRING, prediction_time TIMESTAMP_LTZ(3), feature_version STRING,
          speed_kmh DOUBLE, speed_mean_15m DOUBLE, speed_mean_30m DOUBLE,
          speed_mean_60m DOUBLE, speed_std_60m DOUBLE, speed_change_kmh DOUBLE,
          precipitation_mm DOUBLE, event_severity INT, neighbor_mean_speed_kmh DOUBLE
        ) WITH (
          'connector' = 'kafka', 'topic' = 'traffic.features.v1',
          'properties.bootstrap.servers' = '{bootstrap_servers}',
          'key.fields' = 'road_id', 'key.format' = 'json', 'value.format' = 'json',
          'value.fields-include' = 'ALL'
        )
        """
    )
    result = tables.execute_sql(
        """
        INSERT INTO traffic_features
        SELECT event_id, event_time, CURRENT_TIMESTAMP, 'flink-traffic-features', event_id, schema_version,
          road_id, city, available_at, '1', speed_kmh,
          mean_15m(event_time, speed_kmh) OVER w60,
          mean_30m(event_time, speed_kmh) OVER w60,
          AVG(speed_kmh) OVER w60,
          STDDEV_POP(speed_kmh) OVER w60, speed_kmh - FIRST_VALUE(speed_kmh) OVER w60,
          CAST(NULL AS DOUBLE), 0, CAST(NULL AS DOUBLE)
        FROM traffic_observations
        WINDOW w60 AS (PARTITION BY road_id ORDER BY event_time
          RANGE BETWEEN INTERVAL '60' MINUTE PRECEDING AND CURRENT ROW)
        """
    )
    result.wait()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a streaming platform process")
    parser.add_argument("process", choices=("normalize", "archive", "features"))
    parser.add_argument("--bootstrap-servers", default="kafka:29092")
    parser.add_argument("--checkpoint-uri", default="s3://cognitive-traffic/checkpoints/traffic-features")
    args = parser.parse_args()
    if args.process == "normalize":
        run_normalizer()
    elif args.process == "archive":
        run_archive()
    else:
        run_flink_features(args.bootstrap_servers, args.checkpoint_uri)


if __name__ == "__main__":
    main()
