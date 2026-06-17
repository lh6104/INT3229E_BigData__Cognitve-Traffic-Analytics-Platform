"""Feature selection helpers shared by notebooks and CLI training."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


NON_FEATURE_COLUMNS = {
    "target",
    "target_speed",
    "target_speed_15m",
    "target_speed_60m",
    "future_speed_15m",
    "future_speed_60m",
    "future_speed_240m",
    "timestamp",
    "time_bucket",
    "time_bucket_local",
    "prediction",
    "predicted_speed_kph",
    "actual_target_speed_kph",
    "horizon",
    "task",
    "model",
    "split",
}


@dataclass(frozen=True)
class FeatureSelection:
    feature_columns: list[str]
    numeric_columns: list[str]
    categorical_columns: list[str]
    target_column: str


def infer_target_column(df: pd.DataFrame, preferred: str | None = None) -> str:
    """Infer a target column from local Gold training datasets."""
    candidates = [preferred] if preferred else []
    candidates.extend(["target_speed", "target_speed_15m", "future_speed_15m"])
    for column in candidates:
        if column and column in df.columns:
            return column
    raise ValueError(
        "Could not infer target column. Pass --target-column or ensure one of "
        "target_speed, target_speed_15m, future_speed_15m exists."
    )


def select_feature_columns(
    df: pd.DataFrame,
    target_column: str,
    exclude_columns: set[str] | None = None,
) -> FeatureSelection:
    """Select model features while excluding identifiers, targets, and leakage columns."""
    excluded = set(NON_FEATURE_COLUMNS)
    excluded.add(target_column)
    if exclude_columns:
        excluded.update(exclude_columns)

    feature_columns = [
        column
        for column in df.columns
        if column not in excluded
        and not column.startswith("target_speed_")
        and not column.startswith("future_speed_")
    ]
    numeric_columns = df[feature_columns].select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical_columns = [column for column in feature_columns if column not in numeric_columns]
    return FeatureSelection(
        feature_columns=feature_columns,
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        target_column=target_column,
    )


def time_ordered_split(
    df: pd.DataFrame,
    validation_fraction: float = 0.2,
    time_column: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split train/validation by time order when possible."""
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1")
    work = df.copy()
    sort_column = time_column
    if sort_column is None:
        sort_column = "time_bucket" if "time_bucket" in work.columns else "timestamp" if "timestamp" in work.columns else None
    if sort_column and sort_column in work.columns:
        work[sort_column] = pd.to_datetime(work[sort_column], errors="coerce")
        work = work.sort_values(sort_column)
    split_index = max(1, int(len(work) * (1 - validation_fraction)))
    return work.iloc[:split_index].copy(), work.iloc[split_index:].copy()
