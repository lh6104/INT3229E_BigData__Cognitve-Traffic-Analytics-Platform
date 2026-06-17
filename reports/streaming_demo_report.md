# Streaming Demo Report

Generated at: `2026-06-17T22:12:24.019640+00:00`
Status: `PASS`
Kafka enabled: `True`
Run ID: `bounded-1781734344`

| Metric | Value |
|---|---:|
| produced | 10 |
| consumed | 45 |
| bronze_written | 9 |
| dlq_written | 1 |
| validation_errors | 1 |

## Topics

| Source | Topic | DLQ topic |
|---|---|---|
| traffic | `traffic.raw` | `traffic.raw.dlq` |
| weather | `weather.raw` | `weather.raw.dlq` |
| news | `news.raw` | `news.raw.dlq` |
