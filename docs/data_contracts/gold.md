# Contract: Gold Feature Dataset

| Field | Type | Nullable | Example | Validation rule | Source | Downstream usage |
|---|---|---:|---|---|---|---|
| city | string | no | hanoi | normalized city key | Silver | API filters |
| segment_id | string | no | HN_005 | non-empty | Silver | serving key |
| time_bucket | timestamp local | no | 2026-06-12 08:20:00 | parseable, ordered per segment | Silver | model features |
| currentSpeed | float | no | 28.4 | 0..150 | Silver | model/API |
| freeFlowSpeed | float | no | 45.0 | 1..180 | Silver | model/API |
| jamFactor | float | no | 6.7 | 0..10 | Silver | hotspots/graph |
| speed_lag_* | float | yes | 27.9 | historical only | feature engineering | model |
| congestion_rolling_avg_* | float | yes | 5.8 | historical window only | feature engineering | model |
| target_speed | float | yes | 31.0 | future exact-horizon join, not serving feature | Gold train files | training |
| split | string | yes | train | train/validation/test | time split | evaluation |
