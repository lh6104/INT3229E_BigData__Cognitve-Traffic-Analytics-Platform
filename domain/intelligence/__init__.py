"""Cognitive intelligence helpers for traffic prediction and alerting."""

from domain.intelligence.prediction_reliability import PredictionReliability, assess_prediction_reliability
from domain.intelligence.risk_scoring import SegmentRisk, score_segment_risk
from domain.intelligence.smart_alert_reasoner import SmartAlertReason, reason_about_alert
from domain.intelligence.what_if_simulator import SimulationResult, simulate_traffic_scenario

__all__ = [
    "PredictionReliability",
    "SegmentRisk",
    "SimulationResult",
    "SmartAlertReason",
    "assess_prediction_reliability",
    "reason_about_alert",
    "score_segment_risk",
    "simulate_traffic_scenario",
]
