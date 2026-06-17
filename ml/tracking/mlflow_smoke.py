"""Verify MLflow tracking server by creating a tiny run."""

from __future__ import annotations

import argparse
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracking-uri", default=os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    parser.add_argument("--experiment", default=os.getenv("MLFLOW_EXPERIMENT_NAME", "cognitive-traffic-local"))
    args = parser.parse_args()

    try:
        import mlflow
    except Exception as exc:
        print(f"FAIL mlflow import: {exc}")
        return 1

    try:
        mlflow.set_tracking_uri(args.tracking_uri)
        mlflow.set_experiment(args.experiment)
        with mlflow.start_run(run_name=f"smoke-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"):
            mlflow.log_metric("smoke_metric", 1.0)
            mlflow.log_param("component", "mlflow-test")
            with tempfile.TemporaryDirectory() as tmp:
                artifact = Path(tmp) / "smoke.txt"
                artifact.write_text("mlflow smoke artifact\n", encoding="utf-8")
                mlflow.log_artifact(str(artifact), artifact_path="smoke")
        print(f"PASS mlflow tracking uri={args.tracking_uri} experiment={args.experiment}")
        return 0
    except Exception as exc:
        print(f"FAIL mlflow tracking: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
