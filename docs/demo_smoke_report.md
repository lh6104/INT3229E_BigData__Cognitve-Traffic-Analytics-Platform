# Demo Smoke Report

Generated at: 2026-06-11T20:42:35.597874+00:00
Base URL: `http://localhost:8000`

| Check | Status | Detail |
|---|---|---|
| API health | PASS | 200 OK |
| Dashboard summary | PASS | summary returned |
| GeoJSON features | PASS | 75 features |
| Traffic segments | PASS | segments > 0 |
| Forecast 15m | PASS | model=lightgbm_main, coverage=52/67, latency_ms=45.0 |
| Forecast 60m | PASS | model=lightgbm_main, coverage=52/67, latency_ms=22.4 |
| Predicted hotspots | PASS | risk list returned |
| Model status | PASS | model status returned |
| System status | PASS | system status returned |
| Frontend build | SKIPPED | bun is not installed |

Overall status: **PASS**

Endpoint failures are real demo blockers. Optional local dependencies such as Bun may be marked SKIPPED.
