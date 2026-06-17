# API Benchmark

Generated at: `2026-06-17T20:48:26.713165+00:00`
Base URL: `http://127.0.0.1:8001`
Requests per endpoint: `20`

| Endpoint | Success rate | Errors | p50 ms | p95 ms | Min ms | Max ms |
|---|---:|---:|---:|---:|---:|---:|
| `/health` | 100% | 0 | 1.17 | 6.03 | 0.89 | 10.02 |
| `/system/status` | 100% | 0 | 146.47 | 336.0 | 122.29 | 1026.23 |
| `/dashboard/summary?city=hanoi` | 100% | 0 | 18.52 | 21.69 | 16.01 | 22.55 |
| `/traffic/predict/HN_005?horizon=15m` | 100% | 0 | 12.16 | 13.49 | 11.19 | 13.95 |
