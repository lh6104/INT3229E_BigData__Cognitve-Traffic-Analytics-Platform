"""Graph analytics service backed by Neo4j with local Gold fallback."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from api.services.local_data import latest_by_segment, traffic_features


def _neo4j_driver():
    try:
        from neo4j import GraphDatabase
    except Exception:
        return None
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    try:
        return GraphDatabase.driver(uri, auth=(user, password), connection_timeout=2.0)
    except Exception:
        return None


def graph_health() -> dict[str, Any]:
    driver = _neo4j_driver()
    if driver is None:
        return {"status": "degraded", "backend": "local_gold", "neo4j": "unavailable"}
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    try:
        with driver.session(database=database) as session:
            row = session.run(
                """
                MATCH (s:RoadSegment)
                WITH count(s) AS segments
                MATCH ()-[r:CONNECTS_TO]->()
                RETURN segments, count(r) AS relationships
                """
            ).single()
        return {
            "status": "healthy",
            "backend": "neo4j",
            "segments": int(row["segments"]),
            "relationships": int(row["relationships"]),
            "checked_at": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        return {"status": "degraded", "backend": "local_gold", "neo4j": f"unavailable: {exc}"}
    finally:
        driver.close()


def hotspots(limit: int = 10) -> dict[str, Any]:
    driver = _neo4j_driver()
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    if driver is not None:
        try:
            with driver.session(database=database) as session:
                rows = session.run(
                    """
                    MATCH (s:RoadSegment)
                    OPTIONAL MATCH (s)-[:CONNECTS_TO]-(n:RoadSegment)
                    RETURN s.segment_id AS segment_id,
                           s.name AS name,
                           s.city AS city,
                           s.latest_jam_factor AS jam_factor,
                           s.latest_speed AS speed,
                           collect(n.segment_id)[0..5] AS neighbors
                    ORDER BY s.latest_jam_factor DESC
                    LIMIT $limit
                    """,
                    {"limit": limit},
                ).data()
            return {"source": "neo4j", "hotspots": rows}
        except Exception:
            pass
        finally:
            driver.close()

    latest = latest_by_segment(traffic_features()).sort_values("jamFactor", ascending=False).head(limit)
    rows = [
        {
            "segment_id": str(row.segment_id),
            "name": str(getattr(row, "segment_name", row.segment_id)),
            "city": str(row.city),
            "jam_factor": float(row.jamFactor),
            "speed": float(row.currentSpeed),
            "neighbors": [],
        }
        for row in latest.itertuples(index=False)
    ]
    return {"source": "local_gold_fallback", "hotspots": rows}


def neighbors(segment_id: str, limit: int = 10) -> dict[str, Any]:
    driver = _neo4j_driver()
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    if driver is not None:
        try:
            with driver.session(database=database) as session:
                rows = session.run(
                    """
                    MATCH (s:RoadSegment {segment_id: $segment_id})-[:CONNECTS_TO]-(n:RoadSegment)
                    RETURN n.segment_id AS segment_id,
                           n.name AS name,
                           n.city AS city,
                           n.latest_jam_factor AS jam_factor,
                           n.latest_speed AS speed
                    ORDER BY n.latest_jam_factor DESC
                    LIMIT $limit
                    """,
                    {"segment_id": segment_id, "limit": limit},
                ).data()
            return {"source": "neo4j", "segment_id": segment_id, "neighbors": rows}
        except Exception:
            pass
        finally:
            driver.close()

    latest = latest_by_segment(traffic_features())
    candidates = latest[latest["segment_id"].astype(str) != str(segment_id)].sort_values("jamFactor", ascending=False).head(limit)
    rows = [
        {
            "segment_id": str(row.segment_id),
            "name": str(getattr(row, "segment_name", row.segment_id)),
            "city": str(row.city),
            "jam_factor": float(row.jamFactor),
            "speed": float(row.currentSpeed),
        }
        for row in candidates.itertuples(index=False)
    ]
    return {"source": "local_gold_fallback", "segment_id": segment_id, "neighbors": rows}
