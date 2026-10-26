"""Road-neighborhood features without a separate graph infrastructure layer."""

from collections.abc import Iterable

from cognitive_traffic.contracts.traffic import TrafficObservation


def latest_neighbor_mean(
    observations: Iterable[TrafficObservation], neighbor_road_ids: set[str]
) -> float | None:
    latest: dict[str, TrafficObservation] = {}
    for observation in observations:
        if observation.road_id in neighbor_road_ids:
            latest[observation.road_id] = observation
    if not latest:
        return None
    return sum(item.speed_kmh for item in latest.values()) / len(latest)
