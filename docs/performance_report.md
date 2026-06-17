# Performance Report

Generated at: 2026-06-16T19:00:44.125385+00:00
Base URL: `http://localhost:8000`
Runs per endpoint: `20`

| Endpoint | Success rate | p50 ms | p95 ms | Avg ms | Payload KB | Status |
|---|---:|---:|---:|---:|---:|---|
| `/health` | 100% | 7.58 | 12.84 | 8.45 | 0.47 | PASS |
| `/dashboard/summary?city=hanoi` | 100% | 7.04 | 10.85 | 8.82 | 0.26 | PASS |
| `/segments/geojson?city=hanoi` | 100% | 8.96 | 9.83 | 9.04 | 5.07 | PASS |
| `/segments/geojson?city=hcmc` | 100% | 9.27 | 9.66 | 9.2 | 5.11 | PASS |
| `/segments/geojson?city=hcmc&include_demo_coverage=true` | 100% | 43.98 | 51.64 | 46.53 | 231.05 | PASS |
| `/traffic/segments?city=hanoi` | 100% | 8.48 | 10.83 | 9.76 | 1.86 | PASS |
| `/traffic/predict/HN_005?horizon=15m` | 100% | 15.71 | 60.82 | 57.08 | 1.36 | PASS |
| `/traffic/predict/HN_005?horizon=60m` | 100% | 16.48 | 22.65 | 18.15 | 1.36 | PASS |
| `/hotspots/predicted?city=hanoi&horizon=15m` | 100% | 0.61 | 6.08 | 2.44 | 2.39 | PASS |
| `/traffic/model/status?load_models=true` | 100% | 1.46 | 1.78 | 1.51 | 1.33 | PASS |
| `/system/status` | 100% | 161.32 | 175.83 | 163.15 | 2.34 | PASS |

## Notes

- Suitable for local demo: yes
- Production-ready: no
- Bottlenecks: `/hotspots/predicted` uses short-TTL cache for demo responsiveness; cold path still needs precomputed/batch risk scoring before scale-out.

## Extra Metrics

- Model load time: `{'15m': 576.71, '60m': 12.28}` (measured_in_benchmark_process)
- Model inference time: `{'15m': 31.1, '60m': 12.25}` (measured_in_benchmark_process)
- API memory after model load: `307.25` MB (measured_from_procfs)
- Frontend build time: npm run build completed in 7.45s (PASS)
