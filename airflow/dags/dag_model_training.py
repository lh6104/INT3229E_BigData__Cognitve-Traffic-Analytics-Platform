"""Headless model training DAG.

Airflow calls the reusable CLI. The Kaggle/Colab notebook uses the same
underlying training modules, but the scheduler does not execute notebooks.
"""

from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="cta_model_training",
    description="Train traffic forecasting model from local Gold data",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["traffic", "ml", "training"],
) as dag:
    train_model = BashOperator(
        task_id="train_model",
        bash_command=(
            "cd /opt/airflow && "
            "python -m ml.training.train_cli "
            "--input data/gold/train_features_15m.parquet "
            "--output-dir models/artifacts "
            "--metadata-dir models/metadata"
        ),
    )
