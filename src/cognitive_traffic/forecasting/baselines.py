from __future__ import annotations

import pandas as pd


class Persistence:
    name = "persistence"

    def fit(self, frame: pd.DataFrame, target: str) -> Persistence:
        return self

    def predict(self, frame: pd.DataFrame) -> pd.Series:
        if "speed_kmh" not in frame:
            raise ValueError("persistence baseline requires speed_kmh")
        return frame["speed_kmh"].astype(float)


class HistoricalMedian:
    name = "historical_median"

    def __init__(self) -> None:
        self.global_median: float | None = None
        self.road_medians: pd.Series | None = None

    def fit(self, frame: pd.DataFrame, target: str) -> HistoricalMedian:
        self.global_median = float(frame[target].median())
        self.road_medians = frame.groupby("road_id")[target].median()
        return self

    def predict(self, frame: pd.DataFrame) -> pd.Series:
        if self.global_median is None or self.road_medians is None:
            raise RuntimeError("baseline has not been fitted")
        return frame["road_id"].map(self.road_medians).fillna(self.global_median).astype(float)


class SeasonalMedian:
    name = "seasonal_median"

    def __init__(self, time_column: str = "prediction_time") -> None:
        self.time_column = time_column
        self.global_median: float | None = None
        self.medians: pd.Series | None = None

    def _keys(self, frame: pd.DataFrame) -> pd.DataFrame:
        timestamp = pd.to_datetime(frame[self.time_column], utc=True)
        return pd.DataFrame(
            {
                "road_id": frame["road_id"].to_numpy(),
                "weekday": timestamp.dt.weekday.to_numpy(),
                "hour": timestamp.dt.hour.to_numpy(),
            },
            index=frame.index,
        )

    def fit(self, frame: pd.DataFrame, target: str) -> SeasonalMedian:
        keyed = self._keys(frame)
        keyed["target"] = frame[target].to_numpy()
        self.medians = keyed.groupby(["road_id", "weekday", "hour"])["target"].median()
        self.global_median = float(frame[target].median())
        return self

    def predict(self, frame: pd.DataFrame) -> pd.Series:
        if self.medians is None or self.global_median is None:
            raise RuntimeError("baseline has not been fitted")
        keys = self._keys(frame)
        index = pd.MultiIndex.from_frame(keys[["road_id", "weekday", "hour"]])
        values = self.medians.reindex(index).fillna(self.global_median).to_numpy()
        return pd.Series(values, index=frame.index, dtype=float)
