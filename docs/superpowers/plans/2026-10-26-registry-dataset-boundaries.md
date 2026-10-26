# Registry and Dataset Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Execute inline; delegation is not required by this plan.

**Goal:** Định danh đúng 12 điểm và các dataset được duyệt, cung cấp policy live-serving và report readiness có thể tái tạo.

**Architecture:** Pure Pydantic contracts và YAML loaders, một policy không side effect, một CLI report. P1 chưa thay event schema/sinks; P2 gọi policy tại persistence boundary. Chức năng này không phụ thuộc broker, provider API hoặc dataset lớn.

**Tech Stack:** Python 3.11, Pydantic 2, PyYAML và pytest/Ruff hiện có.

**Spec:** [P1 spec](../specs/2026-10-26-registry-dataset-boundaries.md); parent [MVP requirements v1.2](../../requirements/cognitive-traffic-mvp-v1.md).

## Global Constraints

- Đúng 12 điểm hiện tại, 6 điểm mỗi thành phố; giữ ID và tọa độ trong `configs/sources.yaml`.
- Source point ID nhận alias `segment_id`; chưa coi ID này là provider/network identity đã xác minh.
- Dataset benchmark không đủ điều kiện phục vụ live current state.
- Report config chưa là evidence provider coverage/live integration.
- Không thêm dependency, truy cập provider, tải dataset, thay source config hoặc di trú event/DB schema ở P1.
- Working tree đang có thay đổi lớn chưa commit: ghi trạng thái trước sửa, chỉ sửa/stage file thuộc P1, không tự commit các thay đổi của người dùng.

## File Structure

Create `src/cognitive_traffic/contracts/registry.py`: shape validation. Create `src/cognitive_traffic/monitoring/registry.py`: loaders và policy. Create `src/cognitive_traffic/monitoring/registry_report.py`: JSON report/CLI. Create `configs/datasets.yaml`: bốn dataset profiles. Create `tests/unit/test_registry.py` và `tests/unit/test_registry_report.py`. Modify `README.md`: hướng dẫn report có giới hạn rõ.

Không cần sửa `contracts/events.py`, `streaming/topics.py`, `storage/postgres.py` hoặc frontend trong phase này.

## Task 1: Fixed monitoring-point registry

**Files:** Create `contracts/registry.py`, `monitoring/registry.py` dưới package; create `tests/unit/test_registry.py`.

**Interfaces:** Produces `MonitoringPoint(point_id: str, city: Literal['hanoi','hcmc'], weather_cell_id: str, lat: float, lon: float)` và `load_monitoring_points(path: Path) -> tuple[MonitoringPoint, ...]`.

- [x] **Step 1:** Ghi nhận `git status --short` và diff của các file định sửa; đọc S01/S05 cùng `configs/sources.yaml`. Giữ config gốc làm authority cho tọa độ.
- [x] **Step 2:** Viết behavioral tests cho đủ scope và duplicate; bổ sung parametrized cases thiếu/thừa ID, city sai, lat/lon ngoài range và cùng weather cell hợp lệ.

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

- [x] **Step 3:** Chạy `conda run -n traffic python -m pytest tests/unit/test_registry.py -q`; xác nhận fail do interface chưa có, không do dependency/environment. Nếu Conda env chưa tồn tại, ghi blocker môi trường, chưa tự cài dependency lớn.
- [x] **Step 4:** Implement contract và loader; `APPROVED_POINT_IDS` là frozenset đúng 12 ID trong spec, `APPROVED_POINT_CITIES` gắn ID với city. Duplicate được kiểm trước missing/extra để lỗi rõ.

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

Imports: `BaseModel`, `ConfigDict`, `Field` từ pydantic; `Literal` từ typing; `Path` từ pathlib; yaml. Constants lấy danh sách đầy đủ tại mục 2 parent requirements; kiểm thử cũng đối chiếu mọi tọa độ parsed với config, không đổi config để làm test pass.

- [x] **Step 5:** Chạy lại test scope và contract regression hiện có. Review diff để xác nhận không sửa source points. Ghi evidence vào checkpoint P1; chỉ tạo commit task-specific nếu workflow thực thi đã cho phép.

## Task 2: Dataset profiles with measurement semantics

**Files:** Modify package `contracts/registry.py`, `monitoring/registry.py`; create `configs/datasets.yaml`; extend `tests/unit/test_registry.py`.

**Interfaces:** Produces `DatasetProfile` và `load_dataset_profiles(path: Path) -> dict[str, DatasetProfile]`. Field contract: `dataset_id`, `profile_version`, `purpose`, `measurement`, `unit`, `source_reference`, `acquisition_status`, `rights_status`.

- [x] **Step 1:** Viết test profile thật và từ chối flow gắn unit speed. Dùng bốn hàng S02 làm expected values, bổ sung duplicate ID và enum sai.

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

- [x] **Step 2:** Chạy test mới, xác nhận fail do profile/loader chưa có.
- [x] **Step 3:** Thêm contracts extra-forbid/frozen. `purpose` có operational/benchmark; measurement speed/flow/video. Unit policy P1: speed có km/h hoặc mph; flow chỉ source_units_unverified; video chỉ frame. Khi xác minh flow units ở phase sau cần profile/schema update có version.

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

Field enum acquisition_status chỉ configured_unverified/not_acquired ở P1, rights_status chỉ unverified. `profile_version` literal '1', `source_reference` nonempty, dataset_id nonempty. Config có schema_version string '1', profiles list bốn record S02; references lần lượt TomTom Flow documentation, DCRNN repo, UA-DETRAC paper và LargeST repo. Không thêm credential hoặc đánh dấu rights verified chỉ vì README có license.

- [x] **Step 4:** Chạy test profile và registry; inspect serialized profiles để xác nhận status chưa bị biến thành acquired/verified. Review dependency diff: không có dependency mới.

## Task 3: Live-serving eligibility policy

**Files:** Modify package `monitoring/registry.py`; extend `tests/unit/test_registry.py`.

**Interfaces:** Consumes contracts/loaders Tasks 1–2. Produces `may_serve_current(profile: DatasetProfile, *, mode: str, point_id: str, points: tuple[MonitoringPoint, ...]) -> bool`.

- [x] **Step 1:** Viết policy matrix. Benchmark có mode live vẫn phải bị từ chối; replay/reprocess của dataset operational cũng bị từ chối; unknown mode là lỗi thay vì silent fallback.

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

- [x] **Step 2:** Chạy matrix test để xác nhận fail trước implementation; thêm invalid mode và spoofed purpose/unit của profile operational.
- [x] **Step 3:** Implement predicate, không side effect.

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

- [x] **Step 4:** Chạy policy tests. Ghi rõ contract là authorization theo scope dữ liệu, không phải xác nhận source acquisition/quality hay quyền sử dụng. P2 phải gọi nó tại sink; P1 chưa chứng minh benchmark đã được cô lập end-to-end.

## Task 4: Deterministic readiness report and CLI

**Files:** Create package `monitoring/registry_report.py`, `tests/unit/test_registry_report.py`; modify `README.md`.

**Interfaces:** Consumes Tasks 1–3. Produces `build_report(sources: Path, datasets: Path) -> dict[str, object]` và `main(argv: list[str] | None = None) -> int`. CLI module entry `raise SystemExit(main())`.

- [x] **Step 1:** Viết CLI/report tests. Kiểm tra determinism, count/city, unverified mapping, chưa acquire dataset và invalid-config exit 2. Không gọi provider.

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

- [x] **Step 2:** Chạy test trước implementation; xác nhận fail đúng interface.
- [x] **Step 3:** Implement report từ loaders, hash bytes đầu vào và JSON output ổn định. Report datasets là list records gồm fields profile và `eligible_for_live_current` từ policy với mode live và point đầu registry. Không gửi secret hoặc toàn bộ sources YAML ra stdout.

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

`main` dùng argparse với `--sources` default `configs/sources.yaml`, `--datasets` default `configs/datasets.yaml`. Bắt OSError/ValueError/KeyError/TypeError/yaml.YAMLError, in lỗi qua stderr rồi return 2. Thành công `print(json.dumps(report, sort_keys=True, ensure_ascii=False))`, return 0. Không catch lỗi lập trình ngoài các lỗi config/file dự kiến.

- [x] **Step 4:** Chạy tests Task 4, sau đó đúng bộ test P1 và regression `tests/unit/test_contracts.py`. Chạy Ruff chỉ files mới/thay đổi; không lấy lỗi baseline không liên quan làm lý do sửa ngoài scope.
- [x] **Step 5:** Thêm hướng dẫn README và smoke CLI:

```bash
conda run -n traffic python -m cognitive_traffic.monitoring.registry_report
```

Expected: JSON có 12 configured points, 6/6 theo city, mapping unverified, ba benchmark profiles not_acquired; chỉ operational profile đủ policy live-current. Đây là smoke config, chưa là live source verification.

- [x] **Step 6:** Review diff và bàn giao checkpoint: files đã sửa, tests thực chạy, report output, trạng thái policy chưa được enforce ở sink và các bước P2. Nếu commit, stage đúng file task, không `git add .` trong working tree hiện tại.

## Self-review và nghiệm thu

| P1 spec | Task |
|---|---|
| S01 fixed registry | 1 |
| S02 dataset profiles | 2 |
| S03 serving policy | 3 |
| S04 offline report/CLI | 4 |
| S05 acceptance | Tests ở 1–4 và checkpoint cuối |

## Checkpoint thực thi P1 — 2026-10-26

- Hoàn thành point/dataset contracts, loaders, `may_serve_current`, readiness CLI, bốn profile khai báo và hướng dẫn README.
- Xác minh: test suite `conda run -n traffic python -m pytest -q` — 45 passed; có một Starlette deprecation warning từ dependency. Ruff trên các file Python thuộc P1 — passed; CLI smoke — exit 0, 12 điểm (6 Hà Nội/6 TP.HCM), benchmark không đủ điều kiện live current.
- Review độc lập chỉ trong phạm vi P1: không có finding actionable.
- Chưa xác minh provider/road mapping, coverage, quyền sử dụng hoặc artifact dataset; CLI không cung cấp evidence cho các trạng thái đó. `vn-mvp-12` vẫn `configured_unverified`.
- P2 còn phải gọi policy tại persistence sink và bảo đảm replay/reprocess không ghi vào live namespace. Không sửa producer, sink, event/DB schema trong checkpoint này.
- Không gọi provider, không tải dataset và không tạo commit.

Interfaces dùng nhất quán `point_id`, `dataset_id`, `purpose`, `measurement`, `unit`, `mapping_status`. Mọi field/type được định nghĩa trong spec hoặc task; không yêu cầu external data để chạy P1. Parent requirements P2–P8 nằm trong roadmap, chưa được đánh dấu hoàn thành bởi plan này.
