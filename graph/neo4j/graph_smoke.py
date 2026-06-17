"""Verify Neo4j graph data and query endpoints."""

from __future__ import annotations

import argparse
import os

import requests
from neo4j import GraphDatabase


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default=os.getenv("API_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--skip-api", action="store_true")
    args = parser.parse_args()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session(database=database) as session:
            row = session.run(
                """
                MATCH (s:RoadSegment)
                WITH count(s) AS segments
                MATCH ()-[r:CONNECTS_TO]->()
                RETURN segments, count(r) AS relationships
                """
            ).single()
        driver.close()
    except Exception as exc:
        print(f"FAIL neo4j query: {exc}")
        return 1

    segments = int(row["segments"])
    relationships = int(row["relationships"])
    if segments <= 0 or relationships <= 0:
        print(f"FAIL graph empty segments={segments} relationships={relationships}")
        return 1

    if not args.skip_api:
        try:
            health = requests.get(f"{args.api_url}/graph/health", timeout=5)
            hotspots = requests.get(f"{args.api_url}/graph/hotspots?limit=3", timeout=5)
            if health.status_code >= 500 or hotspots.status_code >= 500:
                print(f"FAIL graph api health={health.status_code} hotspots={hotspots.status_code}")
                return 1
            print(
                "PASS graph test "
                f"segments={segments} relationships={relationships} "
                f"api_health={health.status_code} api_hotspots={hotspots.status_code}"
            )
            return 0
        except Exception as exc:
            print(f"FAIL graph API unreachable after Neo4j query passed: {exc}")
            return 1

    print(f"PASS graph test segments={segments} relationships={relationships}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
