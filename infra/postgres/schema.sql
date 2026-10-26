CREATE TABLE IF NOT EXISTS roads (
    road_id text PRIMARY KEY,
    city text NOT NULL,
    name text NOT NULL,
    category text NOT NULL,
    geometry jsonb
);

CREATE TABLE IF NOT EXISTS traffic_observations (
    event_id text PRIMARY KEY,
    road_id text NOT NULL REFERENCES roads(road_id),
    city text NOT NULL,
    event_time timestamptz NOT NULL,
    ingested_at timestamptz NOT NULL,
    speed_kmh double precision NOT NULL CHECK (speed_kmh >= 0),
    free_flow_speed_kmh double precision NOT NULL CHECK (free_flow_speed_kmh > 0),
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    source text NOT NULL,
    schema_version text NOT NULL,
    UNIQUE (source, road_id, event_time)
);
CREATE INDEX IF NOT EXISTS traffic_observations_road_time_idx
    ON traffic_observations (road_id, event_time DESC);

CREATE TABLE IF NOT EXISTS traffic_current (
    road_id text PRIMARY KEY REFERENCES roads(road_id),
    city text NOT NULL,
    event_time timestamptz NOT NULL,
    speed_kmh double precision NOT NULL,
    free_flow_speed_kmh double precision NOT NULL,
    confidence double precision NOT NULL,
    source text NOT NULL
);

CREATE TABLE IF NOT EXISTS forecasts (
    event_id text PRIMARY KEY,
    road_id text NOT NULL REFERENCES roads(road_id),
    city text NOT NULL,
    prediction_time timestamptz NOT NULL,
    target_time timestamptz NOT NULL,
    horizon_minutes integer NOT NULL CHECK (horizon_minutes > 0),
    model_version text NOT NULL,
    feature_version text NOT NULL,
    p10_speed_kmh double precision NOT NULL,
    p50_speed_kmh double precision NOT NULL,
    p90_speed_kmh double precision NOT NULL,
    congestion_probability double precision CHECK (congestion_probability BETWEEN 0 AND 1),
    UNIQUE (road_id, prediction_time, horizon_minutes, model_version)
);
CREATE INDEX IF NOT EXISTS forecasts_road_target_idx ON forecasts (road_id, target_time DESC);

CREATE OR REPLACE VIEW forecast_hotspots AS
SELECT road_id, city, target_time, p50_speed_kmh, congestion_probability, model_version
FROM forecasts
WHERE congestion_probability >= 0.5;

CREATE TABLE IF NOT EXISTS alerts (
    alert_id text PRIMARY KEY,
    road_id text NOT NULL REFERENCES roads(road_id),
    created_at timestamptz NOT NULL,
    alert_type text NOT NULL,
    severity integer NOT NULL CHECK (severity BETWEEN 0 AND 3),
    status text NOT NULL CHECK (status IN ('active', 'acknowledged', 'resolved')),
    reason text NOT NULL
);

CREATE TABLE IF NOT EXISTS prediction_outcomes (
    event_id text PRIMARY KEY,
    prediction_id text NOT NULL REFERENCES forecasts(event_id),
    road_id text NOT NULL REFERENCES roads(road_id),
    model_version text NOT NULL,
    prediction_time timestamptz NOT NULL,
    target_time timestamptz NOT NULL,
    forecast_speed_kmh double precision NOT NULL,
    actual_speed_kmh double precision NOT NULL,
    absolute_error_kmh double precision NOT NULL,
    UNIQUE (prediction_id)
);

CREATE TABLE IF NOT EXISTS model_versions (
    model_name text NOT NULL,
    model_version text NOT NULL,
    stage text NOT NULL CHECK (stage IN ('candidate', 'champion', 'archived')),
    dataset_id text NOT NULL,
    feature_version text NOT NULL,
    git_sha text NOT NULL,
    promoted_at timestamptz,
    PRIMARY KEY (model_name, model_version)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_champion_per_model
    ON model_versions (model_name) WHERE stage = 'champion';

CREATE TABLE IF NOT EXISTS model_performance (
    model_version text NOT NULL,
    horizon_minutes integer NOT NULL,
    window_start timestamptz NOT NULL,
    window_end timestamptz NOT NULL,
    sample_count integer NOT NULL,
    mae double precision NOT NULL,
    rmse double precision NOT NULL,
    bias double precision NOT NULL,
    PRIMARY KEY (model_version, horizon_minutes, window_start, window_end)
);

CREATE TABLE IF NOT EXISTS data_quality_metrics (
    measured_at timestamptz NOT NULL,
    stream text NOT NULL,
    events_received bigint NOT NULL,
    invalid_events bigint NOT NULL,
    duplicates bigint NOT NULL,
    late_events bigint NOT NULL,
    freshness_p95_seconds double precision,
    roads_reporting integer,
    expected_roads integer,
    PRIMARY KEY (measured_at, stream)
);
