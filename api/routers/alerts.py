"""Alert management endpoints backed by local Gold data and JSON state."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.services.local_data import DATA_DIR, DataUnavailableError, latest_by_segment, normalize_city, severity_from_jam, traffic_features
from domain.intelligence.risk_scoring import score_segment_risk
from domain.intelligence.smart_alert_reasoner import reason_about_alert

logger = logging.getLogger(__name__)

router = APIRouter()
ACTION_STORE = DATA_DIR / "app_alert_actions.json"


class SeverityLevel(str, Enum):
    """Alert severity levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AlertStatus(str, Enum):
    """Local operator state for a generated alert."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"


class Alert(BaseModel):
    """Traffic alert derived from the latest local Gold snapshot."""

    id: str
    alert_id: str
    segment_id: str
    city: str
    severity: SeverityLevel
    reason: str
    horizon: str = "15m"
    predicted_speed: float
    current_speed: float
    baseline_p50: float
    detected_at: datetime
    created_at: datetime
    acknowledged: bool = False
    status: AlertStatus = AlertStatus.ACTIVE
    source: str = "rule"
    why: List[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None
    affected_segments: List[str] = Field(default_factory=list)
    confidence_level: str = "medium"


class AlertUpdate(BaseModel):
    """Alert status update."""

    acknowledged: bool


class BulkAlertUpdate(BaseModel):
    """Bulk alert status update."""

    ids: List[str]
    acknowledged: bool = True


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_actions(path: Path = ACTION_STORE) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Could not parse alert action store: %s", path)
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): value for key, value in payload.items() if isinstance(value, dict)}


def _write_actions(actions: dict[str, dict[str, str]], path: Path = ACTION_STORE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(actions, indent=2, sort_keys=True), encoding="utf-8")


def _set_alert_status(alert_id: str, status: AlertStatus) -> None:
    actions = _read_actions()
    actions[alert_id] = {"status": status.value, "updated_at": _utcnow()}
    _write_actions(actions)


def _stored_status(alert_id: str, actions: dict[str, dict[str, str]]) -> AlertStatus:
    raw_status = actions.get(alert_id, {}).get("status")
    try:
        return AlertStatus(raw_status) if raw_status else AlertStatus.ACTIVE
    except ValueError:
        return AlertStatus.ACTIVE


def _alert_from_row(row) -> Alert:
    jam = float(row.jamFactor)
    speed = float(row.currentSpeed)
    baseline = float(getattr(row, "p50", getattr(row, "freeFlowSpeed", speed)))
    severity_name = severity_from_jam(jam)
    reason = f"Jam factor {jam:.1f}; speed {speed:.1f} km/h versus baseline {baseline:.1f} km/h"
    risk = score_segment_risk(row)
    smart_reason = reason_about_alert(row, severity_name, risk=risk)
    alert_id = f"alert_{row.city}_{row.segment_id}"
    detected_at = row.timestamp.to_pydatetime()
    return Alert(
        id=alert_id,
        alert_id=alert_id,
        segment_id=str(row.segment_id),
        city=str(row.city),
        severity=SeverityLevel(severity_name),
        reason=reason,
        horizon="15m",
        predicted_speed=round(speed, 2),
        current_speed=round(speed, 2),
        baseline_p50=round(baseline, 2),
        detected_at=detected_at,
        created_at=detected_at,
        acknowledged=False,
        status=AlertStatus.ACTIVE,
        source="rule",
        why=smart_reason.why,
        recommended_action=smart_reason.recommended_action,
        affected_segments=smart_reason.affected_segments,
        confidence_level=smart_reason.confidence_level,
    )


def build_alerts(
    city: Optional[str] = None,
    severity: Optional[SeverityLevel] = None,
    limit: int | None = 50,
) -> list[Alert]:
    """Build visible local alerts and apply persisted operator state."""
    try:
        latest = latest_by_segment(traffic_features(), normalize_city(city) if city else None)
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if latest.empty:
        return []

    latest = latest[latest["jamFactor"] >= 3].sort_values("jamFactor", ascending=False)
    actions = _read_actions()
    alerts = [_alert_from_row(row) for row in latest.itertuples(index=False)]
    for alert in alerts:
        alert.status = _stored_status(alert.alert_id, actions)
        alert.acknowledged = alert.status == AlertStatus.ACKNOWLEDGED
    alerts = [alert for alert in alerts if alert.status != AlertStatus.DISMISSED]
    if severity:
        alerts = [alert for alert in alerts if alert.severity == severity]
    return alerts[:limit] if limit is not None else alerts


def active_alert_count(city: Optional[str] = None) -> int:
    """Count visible alert rows using the same builder as the Alerts page."""
    return len(build_alerts(city=city, limit=None))


@router.get("/active", response_model=List[Alert])
def get_active_alerts(
    city: Optional[str] = None,
    severity: Optional[SeverityLevel] = None,
    limit: int = 50,
):
    """Get locally generated traffic alerts from the latest Gold snapshot."""
    return build_alerts(city=city, severity=severity, limit=limit)


@router.get("/{alert_id}", response_model=Alert)
def get_alert(alert_id: str):
    """Get single alert details."""
    for alert in build_alerts(limit=None):
        if alert.alert_id == alert_id:
            return alert
    raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' was not found in local data")


@router.patch("/{alert_id}/ack", response_model=Alert)
def acknowledge_alert(alert_id: str, update: AlertUpdate):
    """Acknowledge or unacknowledge an alert in local JSON operator state."""
    logger.info("Alert %s acknowledged: %s", alert_id, update.acknowledged)
    _set_alert_status(alert_id, AlertStatus.ACKNOWLEDGED if update.acknowledged else AlertStatus.ACTIVE)
    alert = get_alert(alert_id)
    alert.acknowledged = update.acknowledged
    return alert


@router.patch("/{alert_id}/dismiss", response_model=Alert)
def dismiss_alert(alert_id: str):
    """Dismiss an alert in local JSON operator state."""
    alert = get_alert(alert_id)
    _set_alert_status(alert_id, AlertStatus.DISMISSED)
    alert.status = AlertStatus.DISMISSED
    alert.acknowledged = False
    return alert


@router.patch("/bulk-ack")
def bulk_acknowledge_alerts(update: BulkAlertUpdate):
    """Bulk acknowledge or unacknowledge alerts in local JSON operator state."""
    logger.info("Bulk acknowledged %s alerts: %s", len(update.ids), update.acknowledged)
    status = AlertStatus.ACKNOWLEDGED if update.acknowledged else AlertStatus.ACTIVE
    for alert_id in update.ids:
        _set_alert_status(alert_id, status)
    return {
        "updated_count": len(update.ids),
        "acknowledged": update.acknowledged,
    }
