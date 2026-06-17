"""Lightweight Airflow DAG verification that works without a running scheduler."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DAG_PATH = PROJECT_ROOT / "airflow" / "dags" / "dag_production_like_local_pipeline.py"
REQUIRED_TASKS = {
    "validate_bronze",
    "build_silver",
    "build_gold",
    "run_data_quality",
    "publish_pipeline_report",
}


def main() -> int:
    if not DAG_PATH.exists():
        print(f"FAIL DAG missing: {DAG_PATH}")
        return 1
    try:
        tree = ast.parse(DAG_PATH.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        print(f"FAIL DAG syntax: {exc}")
        return 1
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    missing = sorted(task for task in REQUIRED_TASKS if task not in literals)
    if missing:
        print(f"FAIL DAG task ids missing: {missing}")
        return 1
    print(f"PASS airflow dag smoke path={DAG_PATH.relative_to(PROJECT_ROOT)} tasks={sorted(REQUIRED_TASKS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
