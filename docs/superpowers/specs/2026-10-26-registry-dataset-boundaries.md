# P1 — registry and dataset boundaries

Date: 2026-10-26. Scope: first subsystem of the [MVP roadmap](../plans/2026-10-26-cognitive-traffic-mvp-roadmap.md). Parent authority: [MVP requirements](../../requirements/cognitive-traffic-mvp-v1.md), D02/B01/B06 and foundations D03/D08. Describe the exact 12 points, dataset measurement/mode identities and explicit live-serving policy before P2 sink implementation. Config validation/offline reporting is not provider-coverage/live-integration evidence.

## S01. Fixed point registry

Read `configs/sources.yaml`; preserve IDs/coordinates and six points per city. `MonitoringPoint` uses `point_id`, accepting the existing input alias `segment_id`. Point identity does not verify provider segment or physical road direction.

`load_monitoring_points(path)` returns a tuple of 12 points. Reject duplicate/missing/extra IDs, wrong city, out-of-range latitude/longitude and unsupported point fields. RSS source configuration is validated separately; the `sources` section is not a point record.

Preserve parsed coordinates. Report provider/network mapping as `unverified`; do not invent street names, direction or geometry. Use configured weather cells; multiple points may share one cell.

## S02. Dataset profiles

`configs/datasets.yaml`, schema version `1`, declares four profiles:

| dataset_id | purpose | measurement | initial unit | acquisition status |
|---|---|---|---|---|
| `vn-mvp-12` | operational | speed | km/h | configured_unverified |
| `metr-la` | benchmark | speed | mph | not_acquired |
| `ua-detrac` | benchmark | video | frame | not_acquired |
| `largest` | benchmark | flow | source_units_unverified | not_acquired |

Each profile includes source URI/reference, profile version `1` and the table fields. Acquisition status reflects verified project artifacts, not a configured dataset name. Rights/availability remain `unverified` pending dataset-specific checks.

`load_dataset_profiles(path)` returns an ID-keyed mapping; reject duplicate IDs, invalid enums and invalid measurement/unit combinations. Do not import LargeST flow before verifying units/aggregation. The unverified profile remains readable to report research readiness.

## S03. Live-serving eligibility

`may_serve_current(profile, *, mode, point_id, points)` returns True only for dataset `vn-mvp-12`, purpose operational, measurement speed, unit km/h, mode live, and a registered point. Valid modes are live/replay/reprocess; invalid modes raise ValueError.

Replay/reprocess cannot directly update live current state. Benchmark/live remains ineligible. P1 exports and behaviorally tests policy; worker/sink invocation and namespace enforcement belong to P2. Do not claim P1 proves end-to-end isolation.

P1 adds no Kafka-envelope/event/DB fields. The producer/sink phase owns versioned propagation/migrations; avoid partial contract changes that break consumers.

## S04. Reproducible offline report

`python -m cognitive_traffic.monitoring.registry_report` reads registry/profiles and prints JSON. Options: `--sources`, `--datasets`, defaulting to the configurations above. Invalid config exits 2, reports validation on stderr, and emits no valid report on stdout.

Report: schema_version, sources_sha256, datasets_sha256, configured_points=12, points_by_city, point list with mapping_status=unverified, dataset profiles and policy-based live eligibility. Never expose API keys/credentials, fabricated observation/coverage timestamps, or claims of downloaded data. Identical input bytes yield stable content/order; no current-time field may break determinism.

Later acquisition/mapping verification belongs in separately referenced evidence. P1 reports declarations and does not query providers. Save optional report files under `.local/`.

## S05. P1 acceptance

- Exactly 12 original IDs/coordinates/cities; no added points.
- Detect duplicate/missing/extra ID, invalid coordinate/city/profile.
- Correctly show unknown mapping and unacquired datasets.
- Benchmark/replay/reprocess/unknown-point cases fail current-serving policy.
- Stable CLI digests/exit behavior; infer no source-data acquisition or rights.
- Existing `configs/sources.yaml` consumers continue working; P1 changes no production event contracts.

## File responsibility

| Path | Responsibility |
|---|---|
| `contracts/registry.py` | MonitoringPoint, enums, DatasetProfile, shape and measurement/unit validation |
| `monitoring/registry.py` | Config loading, 12-point invariant, may_serve_current |
| `monitoring/registry_report.py` | Report/CLI without external-source calls |
| `configs/datasets.yaml` | Dataset identity/purpose/measurement/declaration status |
| `tests/unit/test_registry.py` | Scope/profile/serving-policy behavior |
| `tests/unit/test_registry_report.py` | CLI determinism/config errors/evidence labels |

Python paths are relative to `src/cognitive_traffic`; config/test paths are relative to repository root. Historical complete edition is available at Git revision `43ac84e62ec06a0a92429d1db5d87ca056f6b804`; this is the canonical English edition.
