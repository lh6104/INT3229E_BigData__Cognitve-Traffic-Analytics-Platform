# API Benchmark

Generated at: `2026-06-17T22:12:14.029851+00:00`
Base URL: `http://localhost:8000`
Requests per endpoint: `20`

| Endpoint | Success rate | Errors | p50 ms | p95 ms | Min ms | Max ms |
|---|---:|---:|---:|---:|---:|---:|
| `/health` | 100% | 0 | 0.89 | 1.32 | 0.8 | 5.07 |
| `/system/status` | 100% | 0 | 165.34 | 209.81 | 148.26 | 226.04 |
| `/dashboard/summary?city=hanoi` | 100% | 0 | 6.96 | 8.54 | 6.52 | 11.11 |
| `/traffic/predict/HN_005?horizon=15m` | 100% | 0 | 15.97 | 21.79 | 14.4 | 22.91 |
