from datetime import UTC, datetime, timedelta

import pandas as pd

from cognitive_traffic.forecasting.evaluation import Fold
from cognitive_traffic.forecasting.training import train_quantile_bundle


class OneFold:
    def split(self, frame):
        return [
            Fold(
                number=1,
                train_index=frame.index[:16],
                validation_index=frame.index[16:],
                train_start=frame.prediction_time.iloc[0],
                train_end=frame.prediction_time.iloc[15],
                validation_start=frame.prediction_time.iloc[16],
                validation_end=frame.prediction_time.iloc[-1],
            )
        ]


def test_training_compares_baselines_and_emits_ordered_quantiles() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    frame = pd.DataFrame(
        {
            "road_id": ["HN-001"] * 20,
            "prediction_time": [start + timedelta(hours=index) for index in range(20)],
            "speed_kmh": [float(20 + index % 5) for index in range(20)],
            "target_speed_15m": [float(19 + index % 5) for index in range(20)],
        }
    )
    bundle = train_quantile_bundle(frame, targets={15: "target_speed_15m"}, splitter=OneFold())
    names = {row["model"] for row in bundle.metrics}
    assert {"persistence", "historical_median", "seasonal_median", "ridge", "lightgbm_p50"} <= names
    prediction = bundle.predict(frame.iloc[:1], 15).iloc[0]
    assert 0 <= prediction.p10 <= prediction.p50 <= prediction.p90
