SET 'execution.runtime-mode' = 'streaming';
SET 'execution.checkpointing.interval' = '2 s';
SET 'execution.checkpointing.mode' = 'EXACTLY_ONCE';
SET 'table.dml-sync' = 'false';

CREATE TABLE traffic_observations (
  road_id STRING,
  proc_time AS PROCTIME()
) WITH (
  'connector' = 'kafka',
  'topic' = 'flink.smoke.input.v1',
  'properties.bootstrap.servers' = 'kafka:29092',
  'properties.group.id' = 'flink-infrastructure-smoke-v1',
  'scan.startup.mode' = 'latest-offset',
  'format' = 'json',
  'json.ignore-parse-errors' = 'false'
);

CREATE TABLE smoke_counts (
  road_id STRING,
  window_end TIMESTAMP(3),
  event_count BIGINT
) WITH (
  'connector' = 'kafka',
  'topic' = 'flink.smoke.counts.v1',
  'properties.bootstrap.servers' = 'kafka:29092',
  'format' = 'json'
);

INSERT INTO smoke_counts
SELECT road_id, window_end, COUNT(*)
FROM TABLE(
  TUMBLE(TABLE traffic_observations, DESCRIPTOR(proc_time), INTERVAL '5' SECOND)
)
GROUP BY road_id, window_start, window_end;
