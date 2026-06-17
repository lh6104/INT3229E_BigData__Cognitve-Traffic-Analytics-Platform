# Pipeline Run Manifest

Run ID: `local_20260617T221127Z`
Status: `success`
Started at: `2026-06-17T22:11:27.102656+00:00`
Ended at: `2026-06-17T22:11:39.502978+00:00`
Duration seconds: `12.4`

## Stages

| Stage | Status | Duration seconds | Inputs | Outputs | Warnings | Errors |
|---|---|---:|---|---|---|---|
| raw_to_bronze_news | success | 0.722 | `data/raw/events/*.jsonl` | `data/bronze/news_bronze_raw_enhanced` rows=333<br>`data/bronze/news_bronze_quality_report` rows=57 | - | - |
| silver_news_gold_event_features | success | 7.496 | `data/raw/events/*.jsonl`<br>`data/raw/traffic/*.jsonl` | `data/silver/news_events_normalized` rows=333<br>`data/gold/traffic_event_features` rows=3192<br>`data/gold/news_event_quality_report` rows=55 | - | - |
| silver_traffic_weather_gold_features | success | 4.182 | `data/raw/traffic/*.jsonl`<br>`data/raw/weather/*.jsonl` | `data/silver/traffic_cleaned` rows=3192<br>`data/silver/weather_cleaned` rows=601<br>`data/gold/cleaned_traffic_features` rows=3192<br>`data/gold/train_features_15m` rows=1690<br>`data/gold/train_features_60m` rows=910 | - | - |

## Key Outputs

| Dataset | Rows |
|---|---:|
| `data/bronze/news_bronze_raw_enhanced` | 333 |
| `data/silver/traffic_cleaned` | 3192 |
| `data/silver/weather_cleaned` | 601 |
| `data/silver/news_events_normalized` | 333 |
| `data/gold/cleaned_traffic_features` | 3192 |
| `data/gold/traffic_event_features` | 3192 |
| `data/gold/train_features_15m` | 1690 |
| `data/gold/train_features_60m` | 910 |
