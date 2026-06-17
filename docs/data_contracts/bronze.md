# Contract: Bronze Streaming Envelope

Bronze streaming output is append-only JSONL at `data/bronze/streaming_bounded_test.jsonl` for bounded local verification. Batch Bronze news evidence also remains in `data/bronze/`.

| Field | Type | Nullable | Example | Validation rule | Source | Downstream usage |
|---|---|---:|---|---|---|---|
| topic | string | no | traffic.raw | one of traffic.raw/weather.raw/news.raw | Kafka consumer | routing |
| partition | integer | no | 0 | >= 0 | Kafka metadata | replay evidence |
| offset | integer | no | 42 | >= 0 | Kafka metadata | replay evidence |
| idempotency_key | string | no | sha1 | unique per topic/entity/event_time in bounded run | consumer | dedup |
| event_time_utc | timestamp UTC | no | 2026-06-12T01:21:28Z | parseable | payload normalized time | ordering |
| ingested_at_utc | timestamp UTC | no | 2026-06-17T10:00:00Z | parseable | consumer clock | lineage |
| payload | object | no | {...} | validates source topic minimum schema | Kafka value | Silver transforms |
