# Demo Smoke Report

Generated at: 2026-06-17T22:12:04.782120+00:00
Base URL: `http://localhost:8000`

| Check | Status | Detail |
|---|---|---|
| API health | PASS | 200 OK |
| Dashboard summary | PASS | summary returned |
| GeoJSON Hanoi real | PASS | 10 features |
| GeoJSON HCMC real | PASS | 10 features |
| Live Map clean roads | PASS | road-shaped live map segments only |
| Traffic segments | PASS | segments > 0 |
| Forecast 15m | PASS | model=lightgbm_main, coverage=35/67, latency_ms=21.8 |
| Forecast 60m | PASS | model=lightgbm_main, coverage=35/67, latency_ms=15.0 |
| Forecast reliability | PASS | model=lightgbm_main, coverage=35/67, latency_ms=18.7 |
| Predicted hotspots | PASS | risk list returned |
| Model status | PASS | model status returned |
| Graph propagation | PASS | propagation returned |
| Corridor risk | PASS | corridor risk returned |
| System status | PASS | system status returned |
| What-if simulation | PASS | scenario impact returned |
| Frontend build | PASS | npm run build completed in 7.15s |

Overall status: **PASS**

Endpoint failures are real demo blockers. Optional local dependencies such as Bun may be marked SKIPPED.
