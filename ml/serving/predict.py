"""Minimal local artifact prediction helper for notebook-trained models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd


def load_model(path: str | Path) -> Any:
    return joblib.load(path)


def predict(model: Any, features: pd.DataFrame) -> list[float]:
    return [float(value) for value in model.predict(features)]
