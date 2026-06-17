"""Import latest Gold road segments into Neo4j."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import pandas as pd
from neo4j import GraphDatabase

from api.services.local_data import latest_by_segment, traffic_features


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def neo4j_config() -> tuple[str, str, str, str]:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    return uri, user, password, database


def text(value: Any, default: str) -> str:
    if value is None or value != value:
        return default
    value = str(value).strip()
    return value or default


def number(row: pd.Series, key: str, default: float = 0.0) -> float:
    try:
        value = row.get(key, default)
        if value is None or value != value:
            return default
        return float(value)
    except Exception:
        return default


def apply_schema(session) -> None:
    session.run("CREATE CONSTRAINT road_segment_id IF NOT EXISTS FOR (s:RoadSegment) REQUIRE s.segment_id IS UNIQUE").consume()
    session.run("CREATE INDEX road_segment_jam IF NOT EXISTS FOR (s:RoadSegment) ON (s.latest_jam_factor)").consume()
    session.run("CREATE INDEX road_segment_class IF NOT EXISTS FOR (s:RoadSegment) ON (s.road_class)").consume()


def import_rows(limit: int) -> tuple[int, int, int]:
    latest = latest_by_segment(traffic_features())
    if latest.empty:
        raise RuntimeError("No Gold traffic rows available. Run `make pipeline` first.")
    latest = latest.sort_values(["city", "segment_id"]).head(limit).copy()

    uri, user, password, database = neo4j_config()
    driver = GraphDatabase.driver(uri, auth=(user, password))
    segments = 0
    relationships = 0
    with driver.session(database=database) as session:
        apply_schema(session)
        session.run("MATCH ()-[r:CONNECTS_TO]->() DELETE r").consume()
        for _, row in latest.iterrows():
            segment_id = text(row.get("segment_id"), "unknown")
            session.run(
                """
                MERGE (s:RoadSegment {segment_id: $segment_id})
                SET s.name = $name,
                    s.city = $city,
                    s.road_class = $road_class,
                    s.lat = $lat,
                    s.lon = $lon,
                    s.latest_jam_factor = $jam,
                    s.latest_speed = $speed,
                    s.free_flow_speed = $free_flow_speed,
                    s.updated_at = datetime()
                """,
                {
                    "segment_id": segment_id,
                    "name": text(row.get("segment_name"), segment_id),
                    "city": text(row.get("city"), "unknown"),
                    "road_class": text(row.get("road_class_encoded"), "unknown"),
                    "lat": number(row, "lat"),
                    "lon": number(row, "lon"),
                    "jam": number(row, "jamFactor"),
                    "speed": number(row, "currentSpeed"),
                    "free_flow_speed": number(row, "freeFlowSpeed"),
                },
            ).consume()
            segments += 1

        sort_columns = [column for column in ["time_bucket", "timestamp", "segment_id"] if column in latest.columns]
        for city, group in latest.groupby("city"):
            ordered = group.sort_values(sort_columns)["segment_id"].astype(str).drop_duplicates().tolist()
            for upstream, downstream in zip(ordered, ordered[1:]):
                session.run(
                    """
                    MATCH (u:RoadSegment {segment_id: $upstream})
                    MATCH (d:RoadSegment {segment_id: $downstream})
                    MERGE (u)-[:CONNECTS_TO {city: $city}]->(d)
                    """,
                    {"upstream": upstream, "downstream": downstream, "city": str(city)},
                ).consume()
                relationships += 1

        totals = session.run(
            """
            MATCH (s:RoadSegment)
            WITH count(s) AS segments
            MATCH ()-[r:CONNECTS_TO]->()
            RETURN segments, count(r) AS relationships
            """
        ).single()
    driver.close()
    return int(totals["segments"]), int(totals["relationships"]), segments


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    try:
        total_segments, total_relationships, imported = import_rows(args.limit)
    except Exception as exc:
        print(f"FAIL neo4j import: {exc}")
        return 1
    print(
        "PASS neo4j import "
        f"imported={imported} road_segments_total={total_segments} connects_to_total={total_relationships}"
    )
    return 0 if total_segments > 0 and total_relationships > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
