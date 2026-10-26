from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.models.param import Param
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="traffic_historical_replay_v1",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    params={
        "start": Param(type="string", description="Inclusive ISO-8601 start"),
        "end": Param(type="string", description="Exclusive ISO-8601 end"),
        "dataset": Param(default="traffic", enum=["traffic", "weather", "news"]),
    },
    tags=["traffic", "replay", "offline"],
) as dag:
    replay = BashOperator(
        task_id="publish_archived_events",
        bash_command=(
            "python -m cognitive_traffic.streaming.replay "
            "--start '{{ params.start }}' --end '{{ params.end }}' "
            "--dataset '{{ params.dataset }}'"
        ),
    )
