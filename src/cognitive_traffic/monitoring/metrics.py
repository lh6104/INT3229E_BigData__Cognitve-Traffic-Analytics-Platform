from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class QualitySnapshot:
    stream: str
    measured_at: datetime
    events_received: int
    invalid_events: int
    duplicates: int
    late_events: int
    freshness_p95_seconds: float | None
    roads_reporting: int
    expected_roads: int | None

    @property
    def invalid_rate(self) -> float:
        return self.invalid_events / self.events_received if self.events_received else 0.0

    @property
    def duplicate_rate(self) -> float:
        return self.duplicates / self.events_received if self.events_received else 0.0


class StreamQualityWindow:
    def __init__(self, stream: str, *, expected_roads: int | None = None) -> None:
        self.stream = stream
        self.expected_roads = expected_roads
        self.events_received = 0
        self.invalid_events = 0
        self.duplicates = 0
        self.late_events = 0
        self.freshness_seconds: list[float] = []
        self.roads: set[str] = set()

    def observe(
        self,
        *,
        status: str,
        event_time: datetime | None = None,
        observed_at: datetime | None = None,
        road_id: str | None = None,
    ) -> None:
        self.events_received += 1
        if status == "invalid":
            self.invalid_events += 1
        elif status == "duplicate":
            self.duplicates += 1
        elif status == "late":
            self.late_events += 1
        if road_id:
            self.roads.add(road_id)
        if event_time:
            observed_at = observed_at or datetime.now(UTC)
            self.freshness_seconds.append(max(0.0, (observed_at - event_time).total_seconds()))

    def snapshot(self, measured_at: datetime | None = None) -> QualitySnapshot:
        ordered = sorted(self.freshness_seconds)
        p95 = None
        if ordered:
            p95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]
        return QualitySnapshot(
            stream=self.stream,
            measured_at=measured_at or datetime.now(UTC),
            events_received=self.events_received,
            invalid_events=self.invalid_events,
            duplicates=self.duplicates,
            late_events=self.late_events,
            freshness_p95_seconds=p95,
            roads_reporting=len(self.roads),
            expected_roads=self.expected_roads,
        )
