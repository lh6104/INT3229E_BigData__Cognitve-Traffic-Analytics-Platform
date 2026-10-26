"""Daily operational data-quality gate against persisted stream metrics."""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException


@dag(
    dag_id="traffic_data_quality_v1",
    schedule="15 1 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["traffic", "quality"],
)
def data_quality():
    @task
    def check_latest_window() -> None:
        from cognitive_traffic.settings import get_settings
        from cognitive_traffic.storage.postgres import TrafficRepository

        rows = TrafficRepository(get_settings().postgres_dsn).data_quality()
        if not rows:
            raise AirflowFailException("no data-quality metrics have been recorded")
        latest = rows[0]
        received = int(latest["events_received"])
        invalid = int(latest["invalid_events"])
        if received == 0 or invalid / received > 0.05:
            raise AirflowFailException("latest stream window failed the invalid-event threshold")

    check_latest_window()


data_quality()
