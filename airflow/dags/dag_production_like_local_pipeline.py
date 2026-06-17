"""Production-like local Bronze/Silver/Gold orchestration DAG.

This DAG intentionally calls the verified local modules instead of Spark,
Iceberg, Trino, or MinIO placeholders. Heavy lakehouse services remain future
scale-out work until they are wired end to end.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.models.param import Param


PROJECT_DIR = "/opt/airflow"


def validate_bronze_files() -> None:
    from pathlib import Path

    raw = Path(PROJECT_DIR) / "data" / "raw"
    if not (raw / "traffic").exists():
        raise RuntimeError("data/raw/traffic is missing")
    if not list((raw / "traffic").glob("*.jsonl")):
        raise RuntimeError("data/raw/traffic has no JSONL snapshots")


with DAG(
    dag_id="cta_production_like_local_pipeline",
    description="Local Bronze/Silver/Gold + DQ pipeline for Cognitive Traffic Analytics",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
        "execution_timeout": timedelta(minutes=30),
    },
    params={
        "raw_dir": Param("data/raw", type="string"),
        "output_dir": Param("data", type="string"),
        "run_id": Param("airflow_manual", type="string"),
    },
    tags=["traffic", "local", "production-like"],
) as dag:
    validate_bronze = PythonOperator(
        task_id="validate_bronze",
        python_callable=validate_bronze_files,
    )

    build_silver = BashOperator(
        task_id="build_silver",
        bash_command=(
            "set -euo pipefail; cd /opt/airflow; "
            "echo '[cta] running local Bronze/Silver/Gold pipeline'; "
            "python -m pipelines.transformation.run_local_pipeline "
            "--raw-dir '{{ params.raw_dir }}' "
            "--output-dir '{{ params.output_dir }}' "
            "--run-id '{{ params.run_id }}_{{ ts_nodash }}' "
            "--reports-dir reports"
        ),
    )

    build_gold = BashOperator(
        task_id="build_gold",
        bash_command="set -euo pipefail; test -f /opt/airflow/{{ params.output_dir }}/gold/cleaned_traffic_features.parquet",
    )

    run_data_quality = BashOperator(
        task_id="run_data_quality",
        bash_command=(
            "set -euo pipefail; cd /opt/airflow && "
            "python -m pipelines.quality.run_checks "
            "--layer gold "
            "--input '{{ params.output_dir }}/gold/cleaned_traffic_features' "
            "--output reports/data_quality_report.md"
        ),
    )

    publish_pipeline_report = BashOperator(
        task_id="publish_pipeline_report",
        bash_command=(
            "set -euo pipefail; mkdir -p /opt/airflow/reports && "
            "printf '{\"dag_id\":\"cta_production_like_local_pipeline\",\"run_id\":\"%s\",\"completed_at_utc\":\"%s\",\"manifest\":\"reports/pipeline_run_manifest.json\",\"dq_report\":\"reports/data_quality_report.md\"}\\n' "
            "'{{ params.run_id }}_{{ ts_nodash }}' \"$(date -u +%FT%TZ)\" "
            "> /opt/airflow/reports/airflow_run_report.json && "
            "cat /opt/airflow/reports/airflow_run_report.json"
        ),
    )

    validate_bronze >> build_silver >> build_gold >> run_data_quality >> publish_pipeline_report
