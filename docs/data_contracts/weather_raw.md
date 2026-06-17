# Contract: weather.raw

| Field | Type | Nullable | Example | Validation rule | Source | Downstream usage |
|---|---|---:|---|---|---|---|
| city | string | no | hanoi | normalized city key | OpenWeather/raw JSONL | weather join |
| weather_cell_id | string | no | HN_W_01 | non-empty idempotency key component | OpenWeather/raw JSONL | join key |
| event_time | timestamp UTC | no | 2026-06-12T01:21:28Z | parseable timestamp | source timestamp/fallback ingest time | ordering |
| temp | float | yes | 31.2 | -50..60 C | OpenWeather | features |
| humidity | float | yes | 78 | 0..100 | OpenWeather | features/DQ |
| visibility | float | yes | 8000 | 0..10000 m | OpenWeather | features/DQ |
| wind_speed | float | yes | 2.5 | >= 0 | OpenWeather | features |
| rain_1h | float | yes | 0.4 | >= 0 | OpenWeather | risk scoring |
