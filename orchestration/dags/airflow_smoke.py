"""Minimal scheduler, executor, XCom, and logging smoke test."""

from __future__ import annotations

from datetime import UTC, datetime

from airflow.decorators import dag, task


@dag(
    dag_id="airflow_smoke",
    schedule=None,
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    catchup=False,
    tags=["infrastructure", "smoke"],
)
def airflow_smoke():
    @task
    def write_value() -> str:
        value = "airflow-offline-job-ok"
        print(f"smoke value written: {value}")
        return value

    @task
    def check_value(value: str) -> None:
        if value != "airflow-offline-job-ok":
            raise ValueError(f"unexpected smoke value: {value}")
        print(f"smoke value verified: {value}")

    check_value(write_value())


airflow_smoke()
