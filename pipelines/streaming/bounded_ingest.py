"""Bounded Kafka ingestion from local raw snapshots into Bronze JSONL."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOPICS = {
    "traffic": "traffic.raw",
    "weather": "weather.raw",
    "news": "news.raw",
}
DLQ_TOPICS = {topic: f"{topic}.dlq" for topic in TOPICS.values()}
REQUIRED_FIELDS = {
    "traffic.raw": ["city", "segment_id", "currentSpeed", "freeFlowSpeed", "jamFactor"],
    "weather.raw": ["city", "weather_cell_id"],
    "news.raw": ["city"],
}

LOGGER = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def iter_jsonl(paths: Iterable[Path], limit: int) -> Iterable[dict[str, Any]]:
    count = 0
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if count >= limit:
                    return
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                    count += 1
                except json.JSONDecodeError:
                    LOGGER.warning("Skipping invalid JSONL row in %s", path)


def raw_records(raw_dir: Path, source: str, limit: int) -> list[dict[str, Any]]:
    if source == "traffic":
        paths = sorted((raw_dir / "traffic").glob("*.jsonl"), reverse=True)
    elif source == "weather":
        paths = sorted((raw_dir / "weather").glob("*.jsonl"), reverse=True)
    else:
        paths = sorted((raw_dir / "events").glob("*.jsonl"), reverse=True)
    return list(iter_jsonl(paths, limit))


def normalize_record(source: str, record: dict[str, Any], ordinal: int) -> dict[str, Any]:
    event_time = record.get("event_time") or record.get("timestamp") or record.get("published_at_utc") or utc_now()
    payload = dict(record)
    payload["event_time"] = pd_time_iso(event_time)
    payload["source_stream"] = source
    if source == "news":
        payload.setdefault("event_id", payload.get("url") or payload.get("title") or f"news-{ordinal}")
        payload.setdefault("city", "hanoi")
    elif source == "weather":
        payload.setdefault("weather_cell_id", payload.get("cell_id") or payload.get("city") or f"weather-{ordinal}")
        payload.setdefault("city", "hanoi")
    else:
        payload.setdefault("segment_id", payload.get("id") or f"segment-{ordinal}")
        payload.setdefault("city", "hanoi")
    return payload


def pd_time_iso(value: Any) -> str:
    import pandas as pd

    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        ts = pd.Timestamp.now(tz="UTC")
    return ts.isoformat()


def idempotency_key(topic: str, payload: dict[str, Any]) -> str:
    candidates = [
        topic,
        str(payload.get("segment_id") or payload.get("weather_cell_id") or payload.get("event_id") or payload.get("url") or ""),
        str(payload.get("event_time") or payload.get("timestamp") or ""),
    ]
    raw = "|".join(candidates)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def validate(topic: str, payload: dict[str, Any]) -> tuple[bool, str]:
    missing = [field for field in REQUIRED_FIELDS[topic] if field not in payload or payload[field] in {None, ""}]
    if missing:
        return False, f"missing={missing}"
    if topic == "traffic.raw":
        try:
            speed = float(payload["currentSpeed"])
            free_flow = float(payload["freeFlowSpeed"])
            jam = float(payload["jamFactor"])
        except (TypeError, ValueError):
            return False, "numeric traffic fields invalid"
        if not (0 <= speed <= 150 and 1 <= free_flow <= 180 and 0 <= jam <= 10):
            return False, "traffic numeric range invalid"
    return True, "ok"


def build_sample_messages(raw_dir: Path, limit_per_topic: int) -> list[tuple[str, dict[str, Any]]]:
    messages: list[tuple[str, dict[str, Any]]] = []
    for source, topic in TOPICS.items():
        records = raw_records(raw_dir, source, limit_per_topic)
        if not records:
            LOGGER.warning("No raw %s records found under %s", source, raw_dir)
        for ordinal, record in enumerate(records[:limit_per_topic]):
            payload = normalize_record(source, record, ordinal)
            messages.append((topic, payload))
    return messages


def inject_invalid_message(messages: list[tuple[str, dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
    invalid = {
        "city": "hanoi",
        "segment_id": "INVALID_TRAFFIC_DEMO",
        "event_time": utc_now(),
        "currentSpeed": -999,
        "freeFlowSpeed": 40,
        "jamFactor": 99,
        "source_stream": "traffic",
        "injected_invalid": True,
    }
    return [*messages, ("traffic.raw", invalid)]


def write_streaming_report(report: dict[str, Any], reports_dir: Path | None = None) -> None:
    reports_dir = reports_dir or (PROJECT_ROOT / "reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "streaming_demo_report.json"
    md_path = reports_dir / "streaming_demo_report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Streaming Demo Report",
        "",
        f"Generated at: `{report['generated_at']}`",
        f"Status: `{report['overall_status']}`",
        f"Kafka enabled: `{report['kafka_enabled']}`",
        f"Run ID: `{report.get('run_id')}`",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key in ["produced", "consumed", "bronze_written", "dlq_written", "validation_errors"]:
        lines.append(f"| {key} | {report.get(key, 0)} |")
    lines.extend(
        [
            "",
            "## Topics",
            "",
            "| Source | Topic | DLQ topic |",
            "|---|---|---|",
        ]
    )
    for source, topic in TOPICS.items():
        lines.append(f"| {source} | `{topic}` | `{DLQ_TOPICS[topic]}` |")
    if report.get("error"):
        lines.extend(["", "## Error", "", str(report["error"])])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_topics(bootstrap_servers: str, topics: Iterable[str], timeout_ms: int) -> None:
    from kafka import KafkaAdminClient
    from kafka.admin import NewTopic
    from kafka.errors import TopicAlreadyExistsError

    admin = KafkaAdminClient(bootstrap_servers=bootstrap_servers, request_timeout_ms=timeout_ms)
    existing = set(admin.list_topics())
    for topic in topics:
        if topic in existing:
            continue
        try:
            admin.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)])
        except TopicAlreadyExistsError:
            pass
    admin.close()


def produce(bootstrap_servers: str, messages: list[tuple[str, dict[str, Any]]], timeout_ms: int, run_id: str) -> int:
    from kafka import KafkaProducer

    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
        key_serializer=lambda value: value.encode("utf-8"),
        request_timeout_ms=timeout_ms,
    )
    sent = 0
    for topic, payload in messages:
        payload = dict(payload)
        payload["ingestion_run_id"] = run_id
        key = idempotency_key(topic, payload)
        producer.send(topic, key=key, value=payload)
        sent += 1
    producer.flush(timeout=15)
    producer.close()
    return sent


def consume_to_bronze(
    bootstrap_servers: str,
    output: Path,
    expected: int,
    timeout_seconds: int,
    run_id: str,
) -> tuple[int, int, int, int]:
    from kafka import KafkaConsumer
    from kafka import KafkaProducer

    consumer = KafkaConsumer(
        *TOPICS.values(),
        bootstrap_servers=bootstrap_servers,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=1000,
        group_id=f"cta-bounded-{int(time.time())}",
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        key_deserializer=lambda value: value.decode("utf-8") if value else "",
    )
    dlq_producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
        key_serializer=lambda value: value.encode("utf-8"),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    dlq_output = output.with_suffix(".dlq.jsonl")
    seen: set[str] = set()
    read = 0
    written = 0
    dlq_written = 0
    validation_errors = 0
    deadline = time.time() + timeout_seconds
    with output.open("a", encoding="utf-8") as handle, dlq_output.open("a", encoding="utf-8") as dlq_handle:
        while time.time() < deadline and (written + dlq_written) < expected:
            records = consumer.poll(timeout_ms=500, max_records=expected)
            for batch in records.values():
                for record in batch:
                    read += 1
                    payload = record.value
                    if payload.get("ingestion_run_id") != run_id:
                        continue
                    key = record.key or idempotency_key(record.topic, payload)
                    if key in seen:
                        continue
                    seen.add(key)
                    ok, reason = validate(record.topic, payload)
                    if not ok:
                        validation_errors += 1
                        dlq_envelope = {
                            "source_topic": record.topic,
                            "dlq_topic": DLQ_TOPICS[record.topic],
                            "partition": record.partition,
                            "offset": record.offset,
                            "idempotency_key": key,
                            "error": reason,
                            "event_time_utc": pd_time_iso(payload.get("event_time") or payload.get("timestamp")),
                            "ingested_at_utc": utc_now(),
                            "payload": payload,
                        }
                        dlq_producer.send(DLQ_TOPICS[record.topic], key=key, value=dlq_envelope)
                        dlq_handle.write(json.dumps(dlq_envelope, ensure_ascii=False) + "\n")
                        dlq_written += 1
                        LOGGER.warning("Routed invalid consumed %s payload to DLQ: %s", record.topic, reason)
                        continue
                    envelope = {
                        "topic": record.topic,
                        "partition": record.partition,
                        "offset": record.offset,
                        "idempotency_key": key,
                        "event_time_utc": pd_time_iso(payload.get("event_time") or payload.get("timestamp")),
                        "ingested_at_utc": utc_now(),
                        "payload": payload,
                    }
                    handle.write(json.dumps(envelope, ensure_ascii=False) + "\n")
                    written += 1
                    if (written + dlq_written) >= expected:
                        break
                if (written + dlq_written) >= expected:
                    break
    dlq_producer.flush(timeout=15)
    dlq_producer.close()
    consumer.close()
    return read, written, dlq_written, validation_errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    parser.add_argument("--raw-dir", default="raw")
    parser.add_argument("--output", default="data/bronze/streaming_bounded_test.jsonl")
    parser.add_argument("--limit-per-topic", type=int, default=3)
    parser.add_argument("--timeout-ms", type=int, default=5000)
    parser.add_argument("--consume-timeout-seconds", type=int, default=20)
    parser.add_argument("--reset-output", action="store_true")
    parser.add_argument("--inject-invalid", action="store_true", help="Send one invalid traffic message to demonstrate DLQ routing")
    parser.add_argument("--reports-dir", default="reports")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raw_dir = Path(args.raw_dir)
    if not raw_dir.is_absolute():
        raw_dir = PROJECT_ROOT / raw_dir
    output = Path(args.output)
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    if args.reset_output and output.exists():
        output.unlink()
    dlq_output = output.with_suffix(".dlq.jsonl")
    if args.reset_output and dlq_output.exists():
        dlq_output.unlink()

    run_id = f"bounded-{int(time.time())}"
    report = {
        "generated_at": utc_now(),
        "overall_status": "FAIL",
        "kafka_enabled": True,
        "run_id": run_id,
        "topics": TOPICS,
        "dlq_topics": DLQ_TOPICS,
        "produced": 0,
        "consumed": 0,
        "bronze_written": 0,
        "dlq_written": 0,
        "validation_errors": 0,
        "output": str(output.relative_to(PROJECT_ROOT) if output.is_relative_to(PROJECT_ROOT) else output),
        "dlq_output": str(dlq_output.relative_to(PROJECT_ROOT) if dlq_output.is_relative_to(PROJECT_ROOT) else dlq_output),
    }
    reports_dir = Path(args.reports_dir)
    if not reports_dir.is_absolute():
        reports_dir = PROJECT_ROOT / reports_dir
    try:
        create_topics(args.bootstrap_servers, [*TOPICS.values(), *DLQ_TOPICS.values()], args.timeout_ms)
        messages = build_sample_messages(raw_dir, args.limit_per_topic)
        if args.inject_invalid:
            messages = inject_invalid_message(messages)
        sent = produce(args.bootstrap_servers, messages, args.timeout_ms, run_id)
        read, written, dlq_written, validation_errors = consume_to_bronze(
            args.bootstrap_servers,
            output,
            sent,
            args.consume_timeout_seconds,
            run_id,
        )
    except Exception as exc:
        report["error"] = str(exc)
        write_streaming_report(report, reports_dir)
        print(f"FAIL streaming bounded ingestion: {exc}")
        return 1
    report.update(
        {
            "overall_status": "PASS" if sent > 0 and (written + dlq_written) == sent else "FAIL",
            "produced": sent,
            "consumed": read,
            "bronze_written": written,
            "dlq_written": dlq_written,
            "validation_errors": validation_errors,
        }
    )
    write_streaming_report(report, reports_dir)

    print(
        "PASS streaming bounded ingestion "
        f"produced={sent} consumed={read} bronze_written={written} dlq_written={dlq_written} "
        f"validation_errors={validation_errors} output={output} dlq_output={dlq_output} report={reports_dir / 'streaming_demo_report.json'}"
    )
    return 0 if sent > 0 and (written + dlq_written) == sent else 1


if __name__ == "__main__":
    raise SystemExit(main())
