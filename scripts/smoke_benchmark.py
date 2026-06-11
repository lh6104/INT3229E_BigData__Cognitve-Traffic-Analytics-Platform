#!/usr/bin/env python3
"""Measure local demo endpoint latency and write benchmark reports."""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"

ENDPOINTS = [
    "/health",
    "/dashboard/summary?city=hanoi",
    "/segments/geojson?city=hanoi",
    "/traffic/segments?city=hanoi",
    "/traffic/predict/HN_005?horizon=15m",
    "/traffic/predict/HN_005?horizon=60m",
    "/hotspots/predicted?city=hanoi&horizon=15m",
    "/traffic/model/status?load_models=true",
    "/system/status",
]


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def request_once(base_url: str, endpoint: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + endpoint, timeout=timeout) as response:
            body = response.read()
            return {
                "ok": 200 <= response.status < 400,
                "status_code": response.status,
                "latency_ms": (time.perf_counter() - started) * 1000.0,
                "payload_size_kb": len(body) / 1024.0,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return {
            "ok": False,
            "status_code": exc.code,
            "latency_ms": (time.perf_counter() - started) * 1000.0,
            "payload_size_kb": len(body) / 1024.0 if body else 0.0,
            "error": str(exc),
        }
    except Exception as exc:
        return {"ok": False, "status_code": None, "latency_ms": None, "payload_size_kb": 0.0, "error": str(exc)}


def benchmark(base_url: str, runs: int, timeout: float) -> dict[str, Any]:
    endpoint_reports = []
    for endpoint in ENDPOINTS:
        results = [request_once(base_url, endpoint, timeout) for _ in range(runs)]
        successes = [item for item in results if item["ok"] and item["latency_ms"] is not None]
        latencies = [float(item["latency_ms"]) for item in successes]
        payloads = [float(item["payload_size_kb"]) for item in successes]
        endpoint_reports.append(
            {
                "endpoint": endpoint,
                "runs": runs,
                "success_count": len(successes),
                "success_rate": len(successes) / runs if runs else 0.0,
                "status_codes": sorted({item["status_code"] for item in results if item["status_code"] is not None}),
                "p50_ms": round(percentile(latencies, 0.50), 2) if latencies else None,
                "p95_ms": round(percentile(latencies, 0.95), 2) if latencies else None,
                "avg_ms": round(statistics.mean(latencies), 2) if latencies else None,
                "payload_size_kb": round(statistics.mean(payloads), 2) if payloads else None,
                "error": next((item["error"] for item in results if item["error"]), None),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "runs": runs,
        "endpoints": endpoint_reports,
        "extra_metrics": {
            "api_memory_after_model_load": "NOT MEASURED",
            "model_load_time": "NOT MEASURED",
            "model_inference_time": "NOT MEASURED",
            "frontend_build_time": "NOT MEASURED",
        },
    }


def write_reports(report: dict[str, Any]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "performance_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Performance Report",
        "",
        f"Generated at: {report['generated_at']}",
        f"Base URL: `{report['base_url']}`",
        f"Runs per endpoint: `{report['runs']}`",
        "",
        "| Endpoint | Success rate | p50 ms | p95 ms | Avg ms | Payload KB | Status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in report["endpoints"]:
        status = "PASS" if item["success_rate"] == 1.0 else "FAIL" if item["success_rate"] == 0 else "PARTIAL"
        lines.append(
            f"| `{item['endpoint']}` | {item['success_rate'] * 100:.0f}% | "
            f"{item['p50_ms'] if item['p50_ms'] is not None else 'NOT MEASURED'} | "
            f"{item['p95_ms'] if item['p95_ms'] is not None else 'NOT MEASURED'} | "
            f"{item['avg_ms'] if item['avg_ms'] is not None else 'NOT MEASURED'} | "
            f"{item['payload_size_kb'] if item['payload_size_kb'] is not None else 'NOT MEASURED'} | {status} |"
        )
    critical_success = all(item["success_rate"] == 1.0 for item in report["endpoints"][:8])
    lines.extend(
        [
            "",
            "## Notes",
            "",
            f"- Suitable for local demo: {'yes' if critical_success else 'no'}",
            "- Production-ready: no",
            "- Bottlenecks: `/hotspots/predicted` currently performs per-segment prototype inference and should be batch/precomputed before scale-out.",
            "- API memory after model load: NOT MEASURED",
            "- Model load time: NOT MEASURED",
            "- Model inference time: NOT MEASURED",
            "- Frontend build time: NOT MEASURED",
        ]
    )
    (DOCS_DIR / "performance_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    report = benchmark(args.base_url, max(args.runs, 1), args.timeout)
    write_reports(report)
    print("Wrote docs/performance_report.md and docs/performance_report.json")
    return 1 if any(item["success_rate"] == 0 for item in report["endpoints"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
