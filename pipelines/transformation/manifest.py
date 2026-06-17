"""Pipeline run manifest helpers for local portfolio runs."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def table_path(path: Path) -> Path | None:
    if path.is_file():
        return path
    for suffix in [".parquet", ".csv", ".jsonl"]:
        candidate = path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None


def count_rows(path: Path) -> int | None:
    resolved = table_path(path)
    if resolved is None:
        return None
    try:
        if resolved.suffix == ".parquet":
            try:
                import pyarrow.parquet as pq

                return int(pq.ParquetFile(resolved).metadata.num_rows)
            except Exception:
                return int(len(pd.read_parquet(resolved)))
        if resolved.suffix == ".jsonl":
            with resolved.open("r", encoding="utf-8") as handle:
                return sum(1 for line in handle if line.strip())
        return int(sum(len(chunk) for chunk in pd.read_csv(resolved, chunksize=100_000)))
    except Exception:
        try:
            if resolved.suffix == ".parquet":
                return int(len(pd.read_parquet(resolved)))
            if resolved.suffix == ".csv":
                return int(len(pd.read_csv(resolved)))
        except Exception:
            return None
    return None


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def summarize_outputs(paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        resolved = table_path(path)
        rows.append(
            {
                "path": rel(path),
                "resolved_path": rel(resolved) if resolved else None,
                "exists": bool(resolved and resolved.exists()),
                "rows": count_rows(path),
            }
        )
    return rows


def summarize_row_counts(paths: list[Path]) -> dict[str, int | None]:
    return {rel(path): count_rows(path) for path in paths}


def build_stage_record(
    *,
    run_id: str,
    stage_name: str,
    status: str,
    start_time_utc: datetime,
    end_time_utc: datetime,
    input_paths: list[str],
    output_paths: list[Path],
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the stable stage schema consumed by JSON/Markdown reports."""
    output_summaries = summarize_outputs(output_paths)
    stage = {
        "run_id": run_id,
        "stage_name": stage_name,
        "status": status,
        "start_time_utc": start_time_utc.isoformat(),
        "end_time_utc": end_time_utc.isoformat(),
        "duration_seconds": round((end_time_utc - start_time_utc).total_seconds(), 3),
        "input_paths": input_paths,
        "output_paths": [item["path"] for item in output_summaries],
        "row_counts": {item["path"]: item["rows"] for item in output_summaries},
        "warnings": warnings or [],
        "errors": errors or [],
    }
    if extra:
        stage.update(extra)
    return stage


@contextmanager
def manifest_stage(
    stages: list[dict[str, Any]],
    *,
    run_id: str,
    stage_name: str,
    input_paths: list[str],
    output_paths: list[Path],
    reports_dir: Path,
    command: list[str] | None = None,
):
    """Append and persist a stage record, including failed stages before re-raising."""
    start = utc_now()
    perf_start = time.perf_counter()
    try:
        yield
    except Exception as exc:
        end = utc_now()
        stage = build_stage_record(
            run_id=run_id,
            stage_name=stage_name,
            status="failed",
            start_time_utc=start,
            end_time_utc=end,
            input_paths=input_paths,
            output_paths=output_paths,
            errors=[str(exc)],
            extra={"command": command or []},
        )
        stage["duration_seconds"] = round(time.perf_counter() - perf_start, 3)
        stages.append(stage)
        write_manifest({"run_id": run_id, "status": "failed", "stages": stages}, reports_dir)
        raise
    else:
        end = utc_now()
        stage = build_stage_record(
            run_id=run_id,
            stage_name=stage_name,
            status="success",
            start_time_utc=start,
            end_time_utc=end,
            input_paths=input_paths,
            output_paths=output_paths,
            extra={"command": command or []},
        )
        stage["duration_seconds"] = round(time.perf_counter() - perf_start, 3)
        stages.append(stage)


def write_manifest(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "pipeline_run_manifest.json"
    md_path = output_dir / "pipeline_run_manifest.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    started_at = report.get("start_time_utc") or report.get("started_at_utc") or ""
    ended_at = report.get("end_time_utc") or report.get("ended_at_utc") or ""
    lines = [
        "# Pipeline Run Manifest",
        "",
        f"Run ID: `{report['run_id']}`",
        f"Status: `{report['status']}`",
        f"Started at: `{started_at}`",
        f"Ended at: `{ended_at}`",
        f"Duration seconds: `{report.get('duration_seconds', '')}`",
        "",
        "## Stages",
        "",
        "| Stage | Status | Duration seconds | Inputs | Outputs | Warnings | Errors |",
        "|---|---|---:|---|---|---|---|",
    ]
    for stage in report["stages"]:
        inputs = "<br>".join(f"`{item}`" for item in stage.get("input_paths", stage.get("inputs", []))) or "-"
        row_counts = stage.get("row_counts", {})
        output_paths = stage.get("output_paths")
        if output_paths is None:
            output_paths = [item["path"] for item in stage.get("outputs", [])]
            row_counts = {item["path"]: item.get("rows") for item in stage.get("outputs", [])}
        outputs = "<br>".join(
            f"`{path}` rows={row_counts.get(path) if row_counts.get(path) is not None else 'unknown'}"
            for path in output_paths
        ) or "-"
        warnings = "<br>".join(str(item).replace("|", "\\|") for item in stage.get("warnings", [])) or "-"
        errors = "<br>".join(str(item).replace("|", "\\|") for item in stage.get("errors", [])) or "-"
        lines.append(
            f"| {stage.get('stage_name', stage.get('name'))} | {stage['status']} | {stage['duration_seconds']} | "
            f"{inputs} | {outputs} | {warnings} | {errors} |"
        )

    lines.extend(
        [
            "",
            "## Key Outputs",
            "",
            "| Dataset | Rows |",
            "|---|---:|",
        ]
    )
    for item in report.get("key_outputs", []):
        lines.append(f"| `{item['path']}` | {item['rows'] if item['rows'] is not None else 'unknown'} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
