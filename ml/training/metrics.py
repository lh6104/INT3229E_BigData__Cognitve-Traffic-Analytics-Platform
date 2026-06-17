"""Regression metrics shared by notebook and CLI training."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def evaluate_regression(y_true, y_pred) -> dict[str, float | None]:
    """Return standard regression metrics for traffic speed forecasting."""
    y_true_array = np.asarray(y_true, dtype=float)
    y_pred_array = np.asarray(y_pred, dtype=float)
    non_zero = np.abs(y_true_array) > 1e-9
    mape = None
    if non_zero.any():
        mape = float(np.mean(np.abs((y_true_array[non_zero] - y_pred_array[non_zero]) / y_true_array[non_zero])) * 100)
    return {
        "mae": float(mean_absolute_error(y_true_array, y_pred_array)),
        "rmse": float(mean_squared_error(y_true_array, y_pred_array) ** 0.5),
        "mape": mape,
        "r2": float(r2_score(y_true_array, y_pred_array)) if len(y_true_array) > 1 else None,
    }
