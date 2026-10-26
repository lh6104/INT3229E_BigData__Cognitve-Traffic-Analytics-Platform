from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.models.param import Param
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="traffic_lake_compaction_v1",
    schedule="30 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    params={
        "prefix": Param(
            default="canonical/traffic/event_date={{ ds }}/city=hanoi/",
            type="string",
            description="One bounded date/city partition; never a whole dataset",
        ),
        "output_key": Param(
            default="canonical/traffic/event_date={{ ds }}/city=hanoi/compacted.parquet",
            type="string",
        ),
    },
    tags=["traffic", "maintenance", "parquet"],
) as dag:
    compact = BashOperator(
        task_id="compact_partition",
        bash_command=(
            "python -m cognitive_traffic.storage.object_store "
            "--prefix '{{ params.prefix }}' --output-key '{{ params.output_key }}' --delete-sources"
        ),
    )
