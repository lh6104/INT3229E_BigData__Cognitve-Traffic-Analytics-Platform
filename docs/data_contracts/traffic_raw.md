# Contract: traffic.raw

| Field | Type | Nullable | Example | Validation rule | Source | Downstream usage |
|---|---|---:|---|---|---|---|
| city | string | no | hanoi | normalized city key | TomTom/raw JSONL | partition/filter |
| segment_id | string | no | HN_005 | non-empty idempotency key component | TomTom/raw JSONL | joins, graph node |
| event_time | timestamp UTC | no | 2026-06-12T01:21:28Z | parseable timestamp | source timestamp/fallback ingest time | ordering, Bronze |
| currentSpeed | float | no | 28.4 | 0..150 km/h | TomTom flow | features, API |
| freeFlowSpeed | float | no | 45.0 | 1..180 km/h | TomTom flow | congestion ratio |
| jamFactor | float | no | 6.7 | 0..10 | TomTom flow | DQ, hotspots, graph |
| lat | float | yes | 21.03 | valid latitude when present | source metadata | map/graph |
| lon | float | yes | 105.84 | valid longitude when present | source metadata | map/graph |
| segment_name | string | yes | Nguyen Trai | free text | source metadata | dashboard |
