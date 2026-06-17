# Contract: Silver Traffic/Weather

| Field | Type | Nullable | Example | Validation rule | Source | Downstream usage |
|---|---|---:|---|---|---|---|
| city | string | no | hanoi | normalized city key | raw traffic/weather | filter/join |
| segment_id | string | no | HN_005 | non-empty | traffic raw | model/API/graph |
| weather_cell_id | string | yes | HN_W_01 | non-empty when present | traffic/weather raw | weather join |
| time_bucket | timestamp local | no | 2026-06-12 08:20:00 | fixed bucket, parseable | transformation | feature windows |
| currentSpeed | float | no | 28.4 | 0..150 | traffic clean | model/API |
| freeFlowSpeed | float | no | 45.0 | 1..180 | traffic clean | model/API |
| jamFactor | float | no | 6.7 | 0..10 | traffic clean | DQ/hotspots |
| temp | float | yes | 31.2 | -50..60 | weather clean | features |
| humidity | float | yes | 78 | 0..100 | weather clean | features |
