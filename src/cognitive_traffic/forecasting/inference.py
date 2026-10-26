from __future__ import annotations

import io
import os
from datetime import timedelta

import joblib
import pandas as pd

from cognitive_traffic.contracts.events import deterministic_event_id
from cognitive_traffic.contracts.forecasts import Forecast, TrafficFeatures
from cognitive_traffic.forecasting.training import QuantileModelBundle
from cognitive_traffic.settings import get_settings
from cognitive_traffic.storage.object_store import S3ObjectStore
from cognitive_traffic.streaming.producers import ContractProducer
from cognitive_traffic.streaming.topics import TRAFFIC_FEATURES, TRAFFIC_FORECASTS


def congestion_probability(*, threshold_kmh: float, p10: float, p50: float, p90: float) -> float:
    """Approximate P(speed < threshold) with a monotone piecewise quantile CDF."""
    if not 0 <= p10 <= p50 <= p90:
        raise ValueError("quantiles must satisfy 0 <= p10 <= p50 <= p90")
    low_width = max(p50 - p10, 1.0)
    high_width = max(p90 - p50, 1.0)
    if threshold_kmh <= p10:
        probability = 0.1 * (threshold_kmh - max(0.0, p10 - low_width)) / low_width
    elif threshold_kmh <= p50:
        probability = 0.1 + 0.4 * (threshold_kmh - p10) / low_width
    elif threshold_kmh <= p90:
        probability = 0.5 + 0.4 * (threshold_kmh - p50) / high_width
    else:
        probability = 0.9 + 0.1 * (threshold_kmh - p90) / high_width
    return min(1.0, max(0.0, probability))


class Predictor:
    def __init__(self, bundle: QuantileModelBundle, model_version: str) -> None:
        self.bundle = bundle
        self.model_version = model_version

    def forecast(self, features: TrafficFeatures, horizon_minutes: int) -> Forecast:
        values = features.model_dump(mode="python")
        prediction = self.bundle.predict(pd.DataFrame([values]), horizon_minutes).iloc[0]
        target_time = features.prediction_time + timedelta(minutes=horizon_minutes)
        event_id = deterministic_event_id(
            source="forecast-service",
            entity_id=features.road_id,
            event_time=features.prediction_time,
            source_record_id=f"{self.model_version}:{horizon_minutes}",
        )
        return Forecast(
            event_id=event_id,
            road_id=features.road_id,
            city=features.city,
            event_time=features.prediction_time,
            ingested_at=features.ingested_at,
            prediction_time=features.prediction_time,
            target_time=target_time,
            horizon_minutes=horizon_minutes,
            model_version=self.model_version,
            feature_version=features.feature_version,
            p10_speed_kmh=float(prediction.p10),
            p50_speed_kmh=float(prediction.p50),
            p90_speed_kmh=float(prediction.p90),
            source="forecast-service",
            source_record_id=features.event_id,
        )


def load_predictor() -> Predictor:
    settings = get_settings()
    artifact_key = os.environ.get("MODEL_ARTIFACT_KEY")
    model_version = os.environ.get("MODEL_VERSION")
    if not artifact_key or not model_version:
        raise RuntimeError("MODEL_ARTIFACT_KEY and MODEL_VERSION must resolve the promoted model")
    store = S3ObjectStore(
        settings.object_store_uri,
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        region=settings.s3_region,
    )
    bundle = joblib.load(io.BytesIO(store.get_bytes(artifact_key)))
    return Predictor(bundle, model_version)


def run() -> None:
    from confluent_kafka import Consumer

    settings = get_settings()
    predictor = load_predictor()
    producer = ContractProducer(settings.kafka_bootstrap_servers)
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": "forecast-service-v1",
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([TRAFFIC_FEATURES.name])
    try:
        while True:
            message = consumer.poll(1)
            if message is None or message.error() is not None:
                continue
            features = TrafficFeatures.model_validate_json(message.value())
            for horizon in (15, 60, 240):
                producer.send(TRAFFIC_FORECASTS, predictor.forecast(features, horizon))
            producer.flush()
            consumer.commit(message=message, asynchronous=False)
    finally:
        consumer.close()


if __name__ == "__main__":
    run()
