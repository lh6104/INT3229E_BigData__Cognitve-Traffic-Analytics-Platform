#!/usr/bin/env python3
"""Minimal Kafka evidence path for local demo reporting."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"
BRONZE_PATH = PROJECT_ROOT / "data" / "bronze" / "streaming_mini_demo.jsonl"
TOPICS = ["events.news", "traffic.raw", "weather.raw"]


def step(name: str, status: str, evidence: str) -> dict[str, str]:
    return {"step": name, "status": status, "evidence": evidence}


def sample_messages() -> dict[str, list[dict[str, Any]]]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "events.news": [
            {"event_id": f"mini-news-{idx}", "city": "hanoi", "event_category": "traffic", "published_at_utc": now}
            for idx in range(3)
        ],
        "traffic.raw": [
            {"segment_id": f"HN_MINI_{idx:03d}", "city": "hanoi", "currentSpeed": 25 + idx, "timestamp": now}
            for idx in range(3)
        ],
        "weather.raw": [
            {"weather_cell_id": f"HN_W_{idx}", "city": "hanoi", "rain_1h": 0.0, "timestamp": now}
            for idx in range(3)
        ],
    }


def write_reports(report: dict[str, Any]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "streaming_demo_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Streaming Mini Demo Report",
        "",
        f"Generated at: {report['generated_at']}",
        f"Bootstrap servers: `{report['bootstrap_servers']}`",
        "",
        "| Step | Status | Evidence |",
        "|---|---|---|",
    ]
    for current in report["steps"]:
        lines.append(f"| {current['step']} | {current['status']} | {current['evidence']} |")
    lines.extend(
        [
            "",
            f"Overall status: **{report['overall_status']}**",
            "",
            "This is minimal streaming evidence only. It is not a production streaming deployment.",
        ]
    )
    (DOCS_DIR / "streaming_demo_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    parser.add_argument("--timeout-ms", type=int, default=3000)
    args = parser.parse_args()
    steps: list[dict[str, str]] = []
    kafka_enabled = False

    try:
        from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer
        from kafka.admin import NewTopic
        from kafka.errors import TopicAlreadyExistsError
    except Exception as exc:
        steps.append(step("Kafka client import", "SKIPPED", f"kafka-python unavailable: {exc}"))
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "bootstrap_servers": args.bootstrap_servers,
            "kafka_enabled": False,
            "overall_status": "SKIPPED",
            "steps": steps,
        }
        write_reports(report)
        print("Wrote docs/streaming_demo_report.md and docs/streaming_demo_report.json")
        return 0

    try:
        admin = KafkaAdminClient(bootstrap_servers=args.bootstrap_servers, request_timeout_ms=args.timeout_ms)
        existing = set(admin.list_topics())
        steps.append(step("Kafka connection", "PASS", f"connected; existing_topics={len(existing)}"))
        kafka_enabled = True
    except Exception as exc:
        steps.append(step("Kafka connection", "SKIPPED", f"Kafka service not running or unreachable: {exc}"))
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "bootstrap_servers": args.bootstrap_servers,
            "kafka_enabled": False,
            "overall_status": "SKIPPED",
            "steps": steps,
        }
        write_reports(report)
        print("Wrote docs/streaming_demo_report.md and docs/streaming_demo_report.json")
        return 0

    for topic in TOPICS:
        if topic in existing:
            steps.append(step("Topic exists", "PASS", topic))
            continue
        try:
            admin.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)])
            steps.append(step("Topic exists", "PASS", f"created {topic}"))
        except TopicAlreadyExistsError:
            steps.append(step("Topic exists", "PASS", f"{topic} already exists"))
        except Exception as exc:
            steps.append(step("Topic exists", "FAIL", f"{topic}: {exc}"))

    messages = sample_messages()
    sent = 0
    try:
        producer = KafkaProducer(
            bootstrap_servers=args.bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
            request_timeout_ms=args.timeout_ms,
        )
        for topic, topic_messages in messages.items():
            for payload in topic_messages:
                producer.send(topic, payload)
                sent += 1
        producer.flush(timeout=10)
        steps.append(step("Producer sent messages", "PASS", str(sent)))
    except Exception as exc:
        steps.append(step("Producer sent messages", "FAIL", str(exc)))

    consumed: list[dict[str, Any]] = []
    try:
        consumer = KafkaConsumer(
            *TOPICS,
            bootstrap_servers=args.bootstrap_servers,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            consumer_timeout_ms=5000,
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
            group_id=f"cta-mini-demo-{int(time.time())}",
        )
        deadline = time.time() + 6
        for record in consumer:
            consumed.append({"topic": record.topic, "value": record.value})
            if len(consumed) >= sent or time.time() > deadline:
                break
        consumer.close()
        steps.append(step("Consumer read messages", "PASS" if consumed else "FAIL", str(len(consumed))))
    except Exception as exc:
        steps.append(step("Consumer read messages", "FAIL", str(exc)))

    if consumed:
        BRONZE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with BRONZE_PATH.open("w", encoding="utf-8") as handle:
            for record in consumed:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        steps.append(step("Bronze output written", "PASS", f"path={BRONZE_PATH.relative_to(PROJECT_ROOT)} rows={len(consumed)}"))
    else:
        steps.append(step("Bronze output written", "SKIPPED", "no consumed messages"))

    failed = [current for current in steps if current["status"] == "FAIL"]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bootstrap_servers": args.bootstrap_servers,
        "kafka_enabled": kafka_enabled,
        "overall_status": "FAIL" if failed else "PASS",
        "steps": steps,
    }
    write_reports(report)
    print("Wrote docs/streaming_demo_report.md and docs/streaming_demo_report.json")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
