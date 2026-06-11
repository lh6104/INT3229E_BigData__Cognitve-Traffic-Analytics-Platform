# Performance Report

Generated at: 2026-06-11T20:43:06.788060+00:00
Base URL: `http://localhost:8000`
Runs per endpoint: `20`

| Endpoint | Success rate | p50 ms | p95 ms | Avg ms | Payload KB | Status |
|---|---:|---:|---:|---:|---:|---|
| `/health` | 100% | 0.56 | 2.05 | 1.65 | 0.1 | PASS |
| `/dashboard/summary?city=hanoi` | 100% | 22.28 | 49.3 | 38.39 | 0.26 | PASS |
| `/segments/geojson?city=hanoi` | 100% | 37.39 | 77.86 | 44.49 | 476.4 | PASS |
| `/traffic/segments?city=hanoi` | 100% | 26.27 | 31.07 | 25.9 | 8.93 | PASS |
| `/traffic/predict/HN_005?horizon=15m` | 100% | 28.14 | 35.75 | 28.51 | 0.91 | PASS |
| `/traffic/predict/HN_005?horizon=60m` | 100% | 26.28 | 30.57 | 23.76 | 0.91 | PASS |
| `/hotspots/predicted?city=hanoi&horizon=15m` | 100% | 1200.15 | 1296.76 | 1181.9 | 47.57 | PASS |
| `/traffic/model/status?load_models=true` | 100% | 3.93 | 4.85 | 4.24 | 2.27 | PASS |
| `/system/status` | 100% | 357.4 | 409.33 | 367.89 | 1.26 | PASS |

## Notes

- Suitable for local demo: yes
- Production-ready: no
- Bottlenecks: `/hotspots/predicted` currently performs per-segment prototype inference and should be batch/precomputed before scale-out.
- API memory after model load: NOT MEASURED
- Model load time: NOT MEASURED
- Model inference time: NOT MEASURED
- Frontend build time: NOT MEASURED
