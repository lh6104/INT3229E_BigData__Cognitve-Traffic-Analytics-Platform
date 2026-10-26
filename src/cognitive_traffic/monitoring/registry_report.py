"""Offline, deterministic readiness report for configured traffic datasets."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

from cognitive_traffic.monitoring.registry import load_dataset_profiles, load_monitoring_points, may_serve_current


def build_report(sources: Path, datasets: Path) -> dict[str, object]:
    points = load_monitoring_points(sources)
    profiles = load_dataset_profiles(datasets)
    return {
        "schema_version": "1",
        "sources_sha256": hashlib.sha256(sources.read_bytes()).hexdigest(),
        "datasets_sha256": hashlib.sha256(datasets.read_bytes()).hexdigest(),
        "configured_points": len(points),
        "points_by_city": dict(sorted(Counter(point.city for point in points).items())),
        "points": [dict(point.model_dump(), mapping_status="unverified") for point in points],
        "datasets": [
            dict(
                profile.model_dump(),
                eligible_for_live_current=may_serve_current(
                    profile,
                    mode="live",
                    point_id=points[0].point_id,
                    points=points,
                ),
            )
            for profile in profiles.values()
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path("configs/sources.yaml"))
    parser.add_argument("--datasets", type=Path, default=Path("configs/datasets.yaml"))
    args = parser.parse_args(argv)
    try:
        report = build_report(args.sources, args.datasets)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(f"registry report error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
