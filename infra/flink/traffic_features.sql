SET 'execution.runtime-mode' = 'streaming';
SET 'execution.checkpointing.interval' = '2 s';
SET 'execution.checkpointing.mode' = 'EXACTLY_ONCE';
SET 'table.dml-sync' = 'false';
SET 'table.exec.source.idle-timeout' = '5 s';

CREATE TEMPORARY SYSTEM FUNCTION mean_15m AS
  'org.cognitivetraffic.flink.RollingEventTimeMeans$Mean15m';
CREATE TEMPORARY SYSTEM FUNCTION mean_30m AS
  'org.cognitivetraffic.flink.RollingEventTimeMeans$Mean30m';

CREATE TABLE traffic_observations (
  event_id STRING,
  event_time TIMESTAMP_LTZ(3),
  ingested_at TIMESTAMP_LTZ(3),
  source STRING,
  source_record_id STRING,
  schema_version STRING,
  road_id STRING,
  city STRING,
  available_at TIMESTAMP_LTZ(3),
  speed_kmh DOUBLE,
  free_flow_speed_kmh DOUBLE,
  confidence DOUBLE,
  -- Accept up to five minutes of source reordering in the current contract tests.
  -- Older canonical rows remain archived but are intentionally omitted from this feature stream.
  WATERMARK FOR event_time AS event_time - INTERVAL '6' MINUTE
) WITH (
  'connector' = 'kafka',
  'topic' = 'traffic.observation.v1',
  'properties.bootstrap.servers' = 'kafka:29092',
  'properties.group.id' = 'traffic-features-v1',
  'properties.auto.offset.reset' = 'latest',
  'scan.startup.mode' = 'group-offsets',
  'format' = 'json',
  'json.timestamp-format.standard' = 'ISO-8601',
  'json.fail-on-missing-field' = 'true',
  'json.ignore-parse-errors' = 'false'
);

CREATE TABLE traffic_features (
  event_id STRING,
  event_time TIMESTAMP_LTZ(3),
  ingested_at TIMESTAMP_LTZ(3),
  source STRING,
  source_record_id STRING,
  schema_version STRING,
  road_id STRING,
  city STRING,
  prediction_time TIMESTAMP_LTZ(3),
  feature_version STRING,
  speed_kmh DOUBLE,
  speed_mean_15m DOUBLE,
  speed_mean_30m DOUBLE,
  speed_mean_60m DOUBLE,
  speed_std_60m DOUBLE,
  speed_change_kmh DOUBLE,
  precipitation_mm DOUBLE,
  event_severity INT,
  neighbor_mean_speed_kmh DOUBLE
) WITH (
  'connector' = 'kafka',
  'topic' = 'traffic.features.v1',
  'properties.bootstrap.servers' = 'kafka:29092',
  'key.format' = 'json',
  'key.fields' = 'road_id',
  'value.format' = 'json',
  'value.fields-include' = 'ALL',
  'value.json.timestamp-format.standard' = 'ISO-8601'
);

INSERT INTO traffic_features
SELECT
  event_id,
  event_time,
  CURRENT_TIMESTAMP,
  'flink-traffic-features',
  event_id,
  schema_version,
  road_id,
  city,
  available_at,
  '1',
  speed_kmh,
  mean_15m(event_time, speed_kmh) OVER w60,
  mean_30m(event_time, speed_kmh) OVER w60,
  AVG(speed_kmh) OVER w60,
  STDDEV_POP(speed_kmh) OVER w60,
  speed_kmh - FIRST_VALUE(speed_kmh) OVER w60,
  CAST(NULL AS DOUBLE),
  0,
  CAST(NULL AS DOUBLE)
FROM traffic_observations
WINDOW w60 AS (
    PARTITION BY road_id
    ORDER BY event_time
    RANGE BETWEEN INTERVAL '60' MINUTE PRECEDING AND CURRENT ROW
);
