# Limitations

- The system is production-like for local orchestration and integration testing; it is not a hardened production deployment.
- Kafka ingestion is bounded/local and lacks DLQ, schema registry enforcement, retry policy, and lag monitoring.
- MLflow tracking is implemented, but model serving loads local artifacts rather than MLflow Model Registry stages.
- Neo4j graph analytics imports and queries real local segment data, but it is not a production routing engine.
- Some data is snapshot/synthetic/calibrated, so model predictive validity is not proven for real-world operations.
- Spark/Iceberg/Trino/Hive/MinIO remain scale-out future work unless run via the optional lakehouse profile and wired to the pipeline.
