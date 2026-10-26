# Registry and Dataset Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Execute inline; delegation is not required by this plan.

**Goal:** Identify exactly the 12 approved points and datasets, supply live-serving policy and a reproducible readiness report.

**Architecture:** Pure Pydantic contracts, YAML loaders, a side-effect-free policy and a report CLI. P1 does not change event schemas/sinks; P2 invokes policy at the persistence boundary. No broker, provider API or large dataset is required.

**Tech Stack:** Existing Python 3.11, Pydantic 2, PyYAML and pytest/Ruff.

**Spec:** [P1 spec](../specs/2026-10-26-registry-dataset-boundaries.md); parent [MVP requirements v1.2](../../requirements/cognitive-traffic-mvp-v1.md).

## Global Constraints

- Exactly 12 existing points, six per city; preserve IDs and coordinates in `configs/sources.yaml`.
- Source point ID accepts the `segment_id` alias; this does not establish verified provider/network identity.
- Benchmark datasets are ineligible to serve live current state.
- A configuration report is not provider coverage/live-integration evidence.
- P1 adds no dependency, provider calls, dataset downloads, source-config edits or event/DB schema migrations.
- The historical working tree contained substantial uncommitted changes: record state, edit/stage only P1 files and do not commit unrelated user changes.

## File Structure

Create `src/cognitive_traffic/contracts/registry.py`: shape validation. Create `src/cognitive_traffic/monitoring/registry.py`: loaders and policy. Create `src/cognitive_traffic/monitoring/registry_report.py`: JSON report/CLI. Create `configs/datasets.yaml`: four profiles. Create `tests/unit/test_registry.py` and `tests/unit/test_registry_report.py`. Modify `README.md`: report instructions and limitations.

Do not edit `contracts/events.py`, `streaming/topics.py`, `storage/postgres.py` or frontend in this phase.

## Task 1: Fixed monitoring-point registry

**Files:** Create package `contracts/registry.py`, `monitoring/registry.py` and `tests/unit/test_registry.py`.

**Interfaces:** Produces `MonitoringPoint(point_id: str, city: Literal['hanoi','hcmc'], weather_cell_id: str, lat: float, lon: float)` and `load_monitoring_points(path: Path) -> tuple[MonitoringPoint, ...]`.

- [x] **Step 1:** Record `git status --short` and scoped diff; read S01/S05 and `configs/sources.yaml`. Original config is the coordinate authority.
- [x] **Step 2:** Write behavioral scope/duplicate tests; parameterize missing/extra IDs, invalid city, out-of-range coordinates and valid shared weather cells.

```python
from pathlib import Path
from collections import Counter
import pytest
import yaml
from cognitive_traffic.monitoring.registry import load_monitoring_points

def test_configured_registry_has_fixed_scope():
    points = load_monitoring_points(Path('configs/sources.yaml'))
    assert len({p.point_id for p in points}) == 12
    assert Counter(p.city for p in points) == {'hanoi': 6, 'hcmc': 6}
    by_id = {p.point_id: p for p in points}
    assert (by_id['HN_HK_001'].lat, by_id['HN_HK_001'].lon) == (21.0288, 105.8520)
    assert by_id['HCMC_TD_001'].weather_cell_id == by_id['HCMC_CL_001'].weather_cell_id

def test_duplicate_point_is_rejected(tmp_path):
    data = yaml.safe_load(Path('configs/sources.yaml').read_text())
    data['points'].append(data['points'][0])
    path = tmp_path / 'sources.yaml'
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match='duplicate'):
        load_monitoring_points(path)
```

- [x] **Step 3:** Run `conda run -n traffic python -m pytest tests/unit/test_registry.py -q`; confirm failure is the missing interface, not dependencies/environment. If Conda is absent, record that blocker without installing large dependencies.
- [x] **Step 4:** Implement contracts/loaders. `APPROVED_POINT_IDS` is the exact 12-ID frozenset; `APPROVED_POINT_CITIES` maps IDs to cities. Check duplicate before missing/extra for a clear error.

```python
class MonitoringPoint(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, populate_by_name=True)
    point_id: str = Field(alias='segment_id', min_length=1)
    city: Literal['hanoi', 'hcmc']
    weather_cell_id: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)

def load_monitoring_points(path: Path) -> tuple[MonitoringPoint, ...]:
    raw = yaml.safe_load(path.read_text(encoding='utf-8'))
    points = tuple(MonitoringPoint.model_validate(row) for row in raw['points'])
    ids = [p.point_id for p in points]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate monitoring point')
    if set(ids) != APPROVED_POINT_IDS:
        raise ValueError('registry must contain exactly the 12 approved points')
    if any(p.city != APPROVED_POINT_CITIES[p.point_id] for p in points):
        raise ValueError('point city differs from approved registry')
    return tuple(sorted(points, key=lambda point: point.point_id))
```

Imports: `BaseModel`, `ConfigDict`, `Field` from pydantic; `Literal` from typing; `Path` from pathlib; yaml. Constants use the complete parent section-2 ID list. Tests compare every parsed coordinate with config; do not edit config to make tests pass.

- [x] **Step 5:** Rerun scope and existing contract regressions; confirm source points unchanged. Record P1 evidence; commit only task-specific changes if explicitly authorized by the execution workflow.

## Task 2: Dataset profiles with measurement semantics

**Files:** Modify package `contracts/registry.py`, `monitoring/registry.py`; create `configs/datasets.yaml`; extend `tests/unit/test_registry.py`.

**Interfaces:** Produces `DatasetProfile` and `load_dataset_profiles(path: Path) -> dict[str, DatasetProfile]`. Fields: `dataset_id`, `profile_version`, `purpose`, `measurement`, `unit`, `source_reference`, `acquisition_status`, `rights_status`.

- [x] **Step 1:** Test actual profiles and reject flow with speed units. Use the four S02 rows as expected values; add duplicate-ID and invalid-enum cases.

```python
from pydantic import ValidationError
from cognitive_traffic.contracts.registry import DatasetProfile
from cognitive_traffic.monitoring.registry import load_dataset_profiles

def test_profiles_keep_flow_separate_from_speed():
    profiles = load_dataset_profiles(Path('configs/datasets.yaml'))
    assert profiles['metr-la'].unit == 'mph'
    assert profiles['largest'].measurement == 'flow'
    assert profiles['largest'].unit == 'source_units_unverified'
    assert profiles['ua-detrac'].acquisition_status == 'not_acquired'
    with pytest.raises(ValidationError, match='measurement/unit'):
        DatasetProfile(**{**profiles['largest'].model_dump(), 'unit': 'km/h'})
```

- [x] **Step 2:** Run new tests and confirm missing-profile/loader failure.
- [x] **Step 3:** Add extra-forbid/frozen contracts. Purpose: operational/benchmark; measurement: speed/flow/video. P1 units: speed km/h or mph; flow only source_units_unverified; video frame. Verified flow units require a later versioned profile/schema update.

```python
@model_validator(mode='after')
def validate_measurement_unit(self):
    permitted = {
        'speed': {'km/h', 'mph'},
        'flow': {'source_units_unverified'},
        'video': {'frame'},
    }
    if self.unit not in permitted[self.measurement]:
        raise ValueError('measurement/unit mismatch')
    return self

def load_dataset_profiles(path: Path) -> dict[str, DatasetProfile]:
    raw = yaml.safe_load(path.read_text(encoding='utf-8'))
    if raw['schema_version'] != '1':
        raise ValueError('unsupported profile schema_version')
    profiles = [DatasetProfile.model_validate(row) for row in raw['profiles']]
    ids = [p.dataset_id for p in profiles]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate dataset_id')
    return {p.dataset_id: p for p in sorted(profiles, key=lambda p: p.dataset_id)}
```

P1 acquisition_status permits configured_unverified/not_acquired; rights_status only unverified. `profile_version` is literal '1'; source_reference and dataset_id are nonempty. Config schema_version is string '1' with four S02 records; references are TomTom Flow documentation, DCRNN, UA-DETRAC paper and LargeST. Add no credentials; a README license alone does not establish verified rights.

- [x] **Step 4:** Run profile/registry tests; inspect serialization to ensure statuses remain unacquired/unverified. Confirm no new dependencies.

## Task 3: Live-serving eligibility policy

**Files:** Modify package `monitoring/registry.py`; extend `tests/unit/test_registry.py`.

**Interfaces:** Consumes Tasks 1-2 contracts/loaders. Produces `may_serve_current(profile: DatasetProfile, *, mode: str, point_id: str, points: tuple[MonitoringPoint, ...]) -> bool`.

- [x] **Step 1:** Write policy matrix. Benchmark/live and operational/replay/reprocess are rejected; unknown modes raise instead of silently falling back.

```python
from cognitive_traffic.monitoring.registry import may_serve_current

@pytest.mark.parametrize('dataset_id,mode,point_id,expected', [
    ('vn-mvp-12', 'live', 'HN_HK_001', True),
    ('vn-mvp-12', 'replay', 'HN_HK_001', False),
    ('vn-mvp-12', 'reprocess', 'HN_HK_001', False),
    ('vn-mvp-12', 'live', 'unknown', False),
    ('metr-la', 'live', 'HN_HK_001', False),
    ('largest', 'live', 'HN_HK_001', False),
])
def test_current_policy(dataset_id, mode, point_id, expected):
    points = load_monitoring_points(Path('configs/sources.yaml'))
    profiles = load_dataset_profiles(Path('configs/datasets.yaml'))
    assert may_serve_current(profiles[dataset_id], mode=mode, point_id=point_id, points=points) is expected
```

- [x] **Step 2:** Confirm matrix failure before implementation; add invalid mode and spoofed operational purpose/unit.
- [x] **Step 3:** Implement side-effect-free predicate.

```python
def may_serve_current(profile, *, mode, point_id, points):
    if mode not in {'live', 'replay', 'reprocess'}:
        raise ValueError('unsupported execution mode')
    return (
        profile.dataset_id == 'vn-mvp-12'
        and profile.purpose == 'operational'
        and profile.measurement == 'speed'
        and profile.unit == 'km/h'
        and mode == 'live'
        and point_id in {p.point_id for p in points}
    )
```

- [x] **Step 4:** Run policy tests. This authorizes data scope, not acquisition, quality or rights. P2 must call it at the sink; P1 alone does not prove end-to-end benchmark isolation.

## Task 4: Deterministic readiness report and CLI

**Files:** Create package `monitoring/registry_report.py`, `tests/unit/test_registry_report.py`; modify `README.md`.

**Interfaces:** Consumes Tasks 1-3. Produces `build_report(sources: Path, datasets: Path) -> dict[str, object]` and `main(argv: list[str] | None = None) -> int`. Module entry: `raise SystemExit(main())`.

- [x] **Step 1:** Test CLI/report determinism, counts/cities, unverified mapping, unacquired datasets and invalid-config exit 2. No provider calls.

```python
import json
from pathlib import Path
from cognitive_traffic.monitoring.registry_report import build_report, main

def test_report_does_not_invent_coverage():
    args = (Path('configs/sources.yaml'), Path('configs/datasets.yaml'))
    report = build_report(*args)
    assert report == build_report(*args)
    assert report['configured_points'] == 12
    assert report['points_by_city'] == {'hanoi': 6, 'hcmc': 6}
    assert all(p['mapping_status'] == 'unverified' for p in report['points'])
    assert 'reporting_points' not in report

def test_missing_config_returns_exit_two(capsys):
    assert main(['--sources', 'missing-registry.yaml']) == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err
```

- [x] **Step 2:** Run tests before implementation; confirm the expected missing interface.
- [x] **Step 3:** Build report from loaders, hash input bytes and serialize stable JSON. Dataset records contain profile fields plus `eligible_for_live_current` evaluated in live mode against the first registry point. Never print secrets or the full source YAML.

```python
def build_report(sources, datasets):
    points = load_monitoring_points(sources)
    profiles = load_dataset_profiles(datasets)
    return {
        'schema_version': '1',
        'sources_sha256': hashlib.sha256(sources.read_bytes()).hexdigest(),
        'datasets_sha256': hashlib.sha256(datasets.read_bytes()).hexdigest(),
        'configured_points': len(points),
        'points_by_city': dict(sorted(Counter(p.city for p in points).items())),
        'points': [dict(p.model_dump(), mapping_status='unverified') for p in points],
        'datasets': [dict(p.model_dump(), eligible_for_live_current=may_serve_current(
            p, mode='live', point_id=points[0].point_id, points=points
        )) for p in profiles.values()],
    }
```

`main` uses argparse: `--sources` defaults to `configs/sources.yaml`, `--datasets` to `configs/datasets.yaml`. Catch OSError/ValueError/KeyError/TypeError/yaml.YAMLError; print validation errors to stderr and return 2. Success prints `json.dumps(report, sort_keys=True, ensure_ascii=False)` and returns 0. Do not catch unexpected programming errors.

- [x] **Step 4:** Run Task 4 tests, P1 tests and `tests/unit/test_contracts.py` regression. Run Ruff on changed/new files; unrelated baseline failures do not justify out-of-scope edits.
- [x] **Step 5:** Add README instructions and CLI smoke:

```bash
conda run -n traffic python -m cognitive_traffic.monitoring.registry_report
```

Expected: 12 configured points, 6/6 by city, unverified mapping and three not_acquired benchmarks. Only operational profile passes live-current policy. This is configuration smoke, not live-source verification.

- [x] **Step 6:** Review diff and hand off changed files, executed tests/report, policy not yet enforced at sink, and P2 next steps. If authorized to commit, stage only task files; do not use `git add .`.

## Self-review and acceptance

| P1 spec | Task |
|---|---|
| S01 fixed registry | 1 |
| S02 dataset profiles | 2 |
| S03 serving policy | 3 |
| S04 offline report/CLI | 4 |
| S05 acceptance | Tests in Tasks 1-4 and final checkpoint |

## Historical P1 execution checkpoint - 2026-10-26

- Completed point/dataset contracts, loaders, `may_serve_current`, readiness CLI, four declared profiles and README instructions.
- Historical recheck: `conda run -n traffic python -m pytest -q`: 46 passed, one dependency Starlette deprecation warning. Ruff on `src tests orchestration` passed. These are historical results, not validation of later changes.
- Historical P1 human acceptance: two report runs produced identical JSON; 12 points, city counts 6/6, mapping unverified; benchmarks eligible_for_live_current=false, acquisition not_acquired, rights unverified. Duplicate-point config and flow-with-speed-unit profile copies exited 2 without a valid stdout report.
- Historical runtime check: health and `/traffic/current?city=hanoi` returned 200 after stack restart; current body `[]`. No provider key/traffic data, so no live-source integration claim. With API down UI showed unavailable without invented roads; backend recovery required UI reload to clear the prior error.
- Historical independent review scoped only to P1: no actionable findings reported; not a human course peer review.
- Provider/road mapping, coverage, rights and acquired artifacts remained unverified. The CLI cannot establish them; vn-mvp-12 remained configured_unverified.
- P2 still needed sink enforcement and replay/reprocess live-namespace isolation. This checkpoint changed no producer, sink or event/DB schema.
- No provider calls or downloads. P1 implementation commit `104ae05`; PostgreSQL nullable-filter regression fix `ca3467d`.

Interfaces consistently use `point_id`, `dataset_id`, `purpose`, `measurement`, `unit`, `mapping_status`. All fields/types are defined in the spec/tasks; P1 needs no external data. Parent P2-P8 requirements remain in the roadmap and are not completed by this plan.
