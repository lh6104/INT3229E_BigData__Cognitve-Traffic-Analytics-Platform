# Data Quality Report

Generated at: 2026-06-17T22:11:43.644518+00:00
Layer: `gold`
Input: `data/gold/cleaned_traffic_features`
Rows: `3192`

| Check | Status | Critical | Detail |
|---|---|---:|---|
| required_columns | PASS | True | missing=[] |
| null_ratio | PASS | True | threshold=0.05 ratios={'city': 0.0, 'segment_id': 0.0, 'time_bucket': 0.0, 'currentSpeed': 0.0, 'freeFlowSpeed': 0.0, 'jamFactor': 0.0} |
| nullable_contract | PASS | True | non_null_violations={} |
| duplicate_key | PASS | True | key=['city', 'segment_id', 'time_bucket'] duplicates=0 |
| timestamp_order | PASS | True | nulls=0 inversions=0 |
| feature_leakage | PASS | True | suspicious_columns=[] |
| freshness | PASS | False | timestamp_column=time_bucket max_timestamp=2026-06-12T08:15:00+00:00 age_hours=133.95 warning_hours=168 |
| city_type | PASS | True | expected=string invalid_rows=0 |
| segment_id_type | PASS | True | expected=string invalid_rows=0 |
| time_bucket_type | PASS | True | expected=timestamp invalid_rows=0 |
| currentSpeed_type | PASS | True | expected=numeric invalid_rows=0 |
| freeFlowSpeed_type | PASS | True | expected=numeric invalid_rows=0 |
| jamFactor_type | PASS | True | expected=numeric invalid_rows=0 |
| weather_temperature_type | PASS | True | expected=numeric invalid_rows=0 |
| weather_humidity_type | PASS | True | expected=numeric invalid_rows=0 |
| has_any_event_type | PASS | True | expected=numeric invalid_rows=0 |
| news_event_count_1h_type | PASS | True | expected=numeric invalid_rows=0 |
| future_speed_15m_type | PASS | True | expected=numeric invalid_rows=0 |
| future_speed_60m_type | PASS | True | expected=numeric invalid_rows=0 |
| currentSpeed_range | PASS | True | min=0 max=150 bad_rows=0 |
| freeFlowSpeed_range | PASS | True | min=1 max=180 bad_rows=0 |
| jamFactor_range | PASS | True | min=0 max=10 bad_rows=0 |
| weather_temperature_range | PASS | True | min=-50 max=60 bad_rows=0 |
| weather_humidity_range | PASS | True | min=0 max=100 bad_rows=0 |
| has_any_event_range | PASS | True | min=0 max=1 bad_rows=0 |
| news_event_count_1h_range | PASS | True | min=0 max=None bad_rows=0 |
| future_speed_15m_range | PASS | True | min=0 max=150 bad_rows=0 |
| future_speed_60m_range | PASS | True | min=0 max=150 bad_rows=0 |
| weather_feature_coverage | PASS | False | missing_ratios={'weather_temperature': 0.06015037593984962, 'weather_humidity': 0.06015037593984962, 'weather_rain_1h': 0.06015037593984962} warn_threshold=0.2 |
| event_feature_coverage | PASS | False | missing_ratios={'has_any_event': 0.0, 'news_event_count_1h': 0.0, 'max_event_severity_1h': 0.0} warn_threshold=0.2 |
| segment_time_bucket_coverage | PASS | False | {'segments': 147, 'median_buckets': 2.0, 'lowest_segments': {}} |
