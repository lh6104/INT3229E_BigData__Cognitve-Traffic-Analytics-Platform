# Current Architecture

```text
Raw JSONL / live API fallback
  -> Kafka topics traffic.raw, weather.raw, news.raw
  -> bounded streaming consumer
  -> Bronze JSONL evidence
  -> Airflow DAG / local pipeline
  -> Silver cleaned data
  -> Gold features
  -> DQ gate
  -> local training with MLflow tracking
  -> local model artifact
  -> FastAPI
  -> React dashboard

Gold segment metadata
  -> Neo4j import
  -> RoadSegment graph
  -> hotspot/neighborhood queries
  -> FastAPI /graph endpoints
  -> dashboard graph panel
```

Default Docker Compose runs Kafka, Postgres, Redis, Airflow, Neo4j, MLflow, and API. Lakehouse services such as MinIO/Trino are kept behind the `lakehouse` profile because they are not the verified default data path.
