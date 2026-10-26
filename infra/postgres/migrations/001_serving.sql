ALTER TABLE roads ADD COLUMN IF NOT EXISTS anchor_lat double precision;
ALTER TABLE roads ADD COLUMN IF NOT EXISTS anchor_lon double precision;
ALTER TABLE roads ADD COLUMN IF NOT EXISTS monitoring_enabled boolean NOT NULL DEFAULT false;
ALTER TABLE traffic_observations ADD COLUMN IF NOT EXISTS canonical_payload jsonb;
ALTER TABLE traffic_observations ADD COLUMN IF NOT EXISTS dataset_id text;
ALTER TABLE traffic_observations ADD COLUMN IF NOT EXISTS mode text;
ALTER TABLE traffic_current ADD COLUMN IF NOT EXISTS event_id text;
ALTER TABLE traffic_current ADD COLUMN IF NOT EXISTS dataset_id text;
ALTER TABLE traffic_current ADD COLUMN IF NOT EXISTS mode text;
-- Pre-migration rows have no verified operational provenance; keep history but
-- exclude them from the live read model until an eligible event is delivered.
DELETE FROM traffic_current WHERE mode IS DISTINCT FROM 'operational'
    OR dataset_id IS DISTINCT FROM 'vn-mvp-12';
