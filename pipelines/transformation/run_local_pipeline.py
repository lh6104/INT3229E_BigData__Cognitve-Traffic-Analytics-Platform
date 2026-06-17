"""Run the local Bronze/Silver/Gold path used by Airflow and Makefile."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from pipelines.transformation.manifest import count_rows, manifest_stage, summarize_outputs, utc_now, write_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_step(args: list[str]) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, check=True)


def run_stage(
    *,
    run_id: str,
    stages: list[dict],
    reports_dir: Path,
    name: str,
    command: list[str],
    inputs: list[str],
    outputs: list[Path],
) -> None:
    with manifest_stage(
        stages,
        run_id=run_id,
        stage_name=name,
        input_paths=inputs,
        output_paths=outputs,
        reports_dir=reports_dir,
        command=[sys.executable, *command],
    ):
        run_step(command)


def resolve_raw_dir(raw_dir: str) -> str:
    path = Path(raw_dir)
    candidate = path if path.is_absolute() else PROJECT_ROOT / path
    if candidate.exists():
        return raw_dir
    if raw_dir == "data/raw":
        legacy = PROJECT_ROOT / "raw"
        if legacy.exists():
            return "raw"
    return raw_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--reports-dir", default="reports")
    args = parser.parse_args()
    args.raw_dir = resolve_raw_dir(args.raw_dir)

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    reports_dir = Path(args.reports_dir)
    if not reports_dir.is_absolute():
        reports_dir = PROJECT_ROOT / reports_dir

    start_time = utc_now()
    run_id = args.run_id or start_time.strftime("local_%Y%m%dT%H%M%SZ")
    stages = []
    status = "success"
    error = None
    try:
        run_stage(
            run_id=run_id,
            stages=stages,
            reports_dir=reports_dir,
            name="raw_to_bronze_news",
            command=["scripts/build_news_bronze.py", "--raw-dir", args.raw_dir, "--output-dir", args.output_dir],
            inputs=[f"{args.raw_dir}/events/*.jsonl"],
            outputs=[
                output_dir / "bronze" / "news_bronze_raw_enhanced",
                output_dir / "bronze" / "news_bronze_quality_report",
            ],
        )
        run_stage(
            run_id=run_id,
            stages=stages,
            reports_dir=reports_dir,
            name="silver_news_gold_event_features",
            command=["scripts/build_news_event_features.py", "--raw-dir", args.raw_dir, "--output-dir", args.output_dir],
            inputs=[f"{args.raw_dir}/events/*.jsonl", f"{args.raw_dir}/traffic/*.jsonl"],
            outputs=[
                output_dir / "silver" / "news_events_normalized",
                output_dir / "gold" / "traffic_event_features",
                output_dir / "gold" / "news_event_quality_report",
            ],
        )
        run_stage(
            run_id=run_id,
            stages=stages,
            reports_dir=reports_dir,
            name="silver_traffic_weather_gold_features",
            command=["scripts/build_local_gold_dataset.py", "--raw-dir", args.raw_dir, "--output-dir", args.output_dir],
            inputs=[f"{args.raw_dir}/traffic/*.jsonl", f"{args.raw_dir}/weather/*.jsonl"],
            outputs=[
                output_dir / "silver" / "traffic_cleaned",
                output_dir / "silver" / "weather_cleaned",
                output_dir / "gold" / "cleaned_traffic_features",
                output_dir / "gold" / "train_features_15m",
                output_dir / "gold" / "train_features_60m",
            ],
        )
    except Exception as exc:
        status = "failed"
        error = str(exc)
    end_time = utc_now()
    key_outputs = summarize_outputs(
        [
            output_dir / "bronze" / "news_bronze_raw_enhanced",
            output_dir / "silver" / "traffic_cleaned",
            output_dir / "silver" / "weather_cleaned",
            output_dir / "silver" / "news_events_normalized",
            output_dir / "gold" / "cleaned_traffic_features",
            output_dir / "gold" / "traffic_event_features",
            output_dir / "gold" / "train_features_15m",
            output_dir / "gold" / "train_features_60m",
        ]
    )
    manifest = {
        "run_id": run_id,
        "status": status,
        "start_time_utc": start_time.isoformat(),
        "end_time_utc": end_time.isoformat(),
        "duration_seconds": round((end_time - start_time).total_seconds(), 3),
        "raw_dir": args.raw_dir,
        "output_dir": args.output_dir,
        "stages": stages,
        "key_outputs": key_outputs,
        "summary": {
            "gold_rows": count_rows(output_dir / "gold" / "cleaned_traffic_features"),
            "train_15m_rows": count_rows(output_dir / "gold" / "train_features_15m"),
            "train_60m_rows": count_rows(output_dir / "gold" / "train_features_60m"),
        },
    }
    if error:
        manifest["errors"] = [error]
    write_manifest(manifest, reports_dir)
    if status != "success":
        print(f"FAIL local pipeline run_id={run_id}: {error}")
        return 1
    print(f"PASS local pipeline run_id={run_id} manifest={reports_dir / 'pipeline_run_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
