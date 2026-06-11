# Cognitive Capability Report

## Cognitive definition

Cognitive trong project này là context-aware predictive decision support, không phải self-learning autonomous AI.

## Cognitive loop

traffic + weather + event + segment context
-> forecast
-> risk score
-> explanation
-> dashboard/API insight

## Current level

Level 3: prototype predictive decision support.

Hệ thống kết hợp local Gold traffic features, segment/geometry context, weather features, event/news aggregate features, forecast output, và transparent risk scoring để tạo predicted hotspot explanation. Endpoint `/hotspots/predicted` là prototype explainable risk scoring, không phải production risk engine.

## Cognitive surfaces

- Dashboard and Live Map: descriptive traffic state and segment context.
- Forecast API/UI: model-driven 15m/60m predicted speed and feature coverage.
- Predicted Hotspots API: forecast-derived risk score, triggered rules, and context explanation.
- Monitoring/System Status: operational evidence for demo readiness and known gaps.

## Not yet level 4

No automatic feedback loop, no online retraining, no calibrated production risk engine.

## Current limitations

- Event context is integrated from existing Gold event aggregate features and remains prototype/partial.
- Risk score thresholds are transparent and configurable, but not calibrated against production ground truth.
- Forecast reliability still depends on feature coverage from local Gold data.
