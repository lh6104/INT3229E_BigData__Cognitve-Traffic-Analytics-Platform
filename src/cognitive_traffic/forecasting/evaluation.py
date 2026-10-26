from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Fold:
    number: int
    train_index: pd.Index
    validation_index: pd.Index
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp


class WalkForwardSplitter:
    """Expanding-window validation with duration-based folds."""

    def __init__(self, *, minimum_train_days: int = 28, validation_days: int = 7, step_days: int = 7) -> None:
        if min(minimum_train_days, validation_days, step_days) <= 0:
            raise ValueError("walk-forward durations must be positive")
        self.minimum_train_days = minimum_train_days
        self.validation_days = validation_days
        self.step_days = step_days

    def split(self, frame: pd.DataFrame, time_column: str = "prediction_time") -> list[Fold]:
        timestamps = pd.to_datetime(frame[time_column], utc=True, errors="raise")
        start = timestamps.min()
        end = timestamps.max()
        validation_start = start + timedelta(days=self.minimum_train_days)
        folds: list[Fold] = []
        number = 1
        while validation_start <= end:
            validation_end = validation_start + timedelta(days=self.validation_days)
            train_mask = timestamps < validation_start
            validation_mask = (timestamps >= validation_start) & (timestamps < validation_end)
            if train_mask.any() and validation_mask.any():
                folds.append(
                    Fold(
                        number=number,
                        train_index=frame.index[train_mask],
                        validation_index=frame.index[validation_mask],
                        train_start=timestamps[train_mask].min(),
                        train_end=timestamps[train_mask].max(),
                        validation_start=timestamps[validation_mask].min(),
                        validation_end=timestamps[validation_mask].max(),
                    )
                )
                number += 1
            validation_start += timedelta(days=self.step_days)
        if not folds:
            raise ValueError("dataset is too short for the configured walk-forward split")
        return folds


def regression_metrics(actual: Iterable[float], predicted: Iterable[float]) -> dict[str, float]:
    actual_array = np.asarray(list(actual), dtype=float)
    predicted_array = np.asarray(list(predicted), dtype=float)
    if actual_array.size == 0 or actual_array.shape != predicted_array.shape:
        raise ValueError("actual and predicted must have equal non-zero length")
    error = predicted_array - actual_array
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(np.square(error)))),
        "bias": float(np.mean(error)),
    }


def sliced_metrics(frame: pd.DataFrame, *, actual: str, predicted: str) -> pd.DataFrame:
    work = frame.copy()
    timestamp = pd.to_datetime(work["prediction_time"], utc=True)
    work["period"] = np.where(timestamp.dt.hour.isin([7, 8, 9, 16, 17, 18]), "peak", "off_peak")
    work["day_type"] = np.where(timestamp.dt.weekday >= 5, "weekend", "weekday")
    dimensions = [
        column
        for column in (
            "horizon_minutes",
            "city",
            "road_category",
            "period",
            "day_type",
            "weather_condition",
            "has_event",
        )
        if column in work
    ]
    rows: list[dict[str, object]] = []
    for column in dimensions:
        for value, group in work.groupby(column, dropna=False):
            rows.append(
                {
                    "slice": column,
                    "value": str(value),
                    "count": len(group),
                    **regression_metrics(group[actual], group[predicted]),
                }
            )
    return pd.DataFrame(rows)


def pinball_loss(actual: Iterable[float], predicted: Iterable[float], quantile: float) -> float:
    if not 0 < quantile < 1:
        raise ValueError("quantile must be between zero and one")
    error = np.asarray(list(actual), dtype=float) - np.asarray(list(predicted), dtype=float)
    return float(np.mean(np.maximum(quantile * error, (quantile - 1) * error)))
