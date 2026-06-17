#!/usr/bin/env python3
"""Lightweight API benchmark for the verified local FastAPI path."""

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
DEFAULT_ENDPOINTS = [
    "/health",
    "/system/status",
    "/dashboard/summary?city=hanoi",
    "/traffic/predict/HN_005?horizon=15m",
]


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] * (1 - (rank - lower)) + ordered[upper] * (rank - lower)


def request_once(base_url: str, endpoint: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + endpoint, timeout=timeout) as response:
            response.read()
            return {"ok": 200 <= response.status < 400, "status_code": response.status, "latency_ms": (time.perf_counter() - started) * 1000, "error": None}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status_code": exc.code, "latency_ms": (time.perf_counter() - started) * 1000, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "status_code": None, "latency_ms": None, "error": str(exc)}


def summarize_endpoint(base_url: str, endpoint: str, requests: int, timeout: float) -> dict[str, Any]:
    results = [request_once(base_url, endpoint, timeout) for _ in range(requests)]
    latencies = [float(item["latency_ms"]) for item in results if item["ok"] and item["latency_ms"] is not None]
    error_count = len(results) - len(latencies)
    return {
        "endpoint": endpoint,
        "requests": requests,
        "success_rate": round(len(latencies) / requests, 4) if requests else 0.0,
        "error_count": error_count,
        "status_codes": sorted({item["status_code"] for item in results if item["status_code"] is not None}),
        "p50_ms": round(percentile(latencies, 0.50), 2) if latencies else None,
        "p95_ms": round(percentile(latencies, 0.95), 2) if latencies else None,
        "min_ms": round(min(latencies), 2) if latencies else None,
        "max_ms": round(max(latencies), 2) if latencies else None,
        "avg_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "first_error": next((item["error"] for item in results if item["error"]), None),
    }


def write_reports(report: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "api_benchmark.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# API Benchmark",
        "",
        f"Generated at: `{report['generated_at']}`",
        f"Base URL: `{report['base_url']}`",
        f"Requests per endpoint: `{report['requests_per_endpoint']}`",
        "",
        "| Endpoint | Success rate | Errors | p50 ms | p95 ms | Min ms | Max ms |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["endpoints"]:
        lines.append(
            f"| `{item['endpoint']}` | {item['success_rate'] * 100:.0f}% | {item['error_count']} | "
            f"{item['p50_ms'] if item['p50_ms'] is not None else 'NA'} | "
            f"{item['p95_ms'] if item['p95_ms'] is not None else 'NA'} | "
            f"{item['min_ms'] if item['min_ms'] is not None else 'NA'} | "
            f"{item['max_ms'] if item['max_ms'] is not None else 'NA'} |"
        )
    (reports_dir / "api_benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("-n", "--requests", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--reports-dir", default="reports")
    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    if not reports_dir.is_absolute():
        reports_dir = PROJECT_ROOT / reports_dir
    endpoints = [summarize_endpoint(args.base_url, endpoint, max(1, args.requests), args.timeout) for endpoint in DEFAULT_ENDPOINTS]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "requests_per_endpoint": max(1, args.requests),
        "endpoints": endpoints,
    }
    write_reports(report, reports_dir)
    print(f"Wrote {reports_dir / 'api_benchmark.json'} and {reports_dir / 'api_benchmark.md'}")
    return 1 if any(item["success_rate"] == 0 for item in endpoints) else 0


if __name__ == "__main__":
    raise SystemExit(main())
