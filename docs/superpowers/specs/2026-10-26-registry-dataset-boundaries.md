# P1 — registry và ranh giới dataset

- Ngày: 2026-10-26. Scope: subsystem đầu của [roadmap MVP](../plans/2026-10-26-cognitive-traffic-mvp-roadmap.md).
- Parent authority: [yêu cầu MVP v1.1](../../requirements/cognitive-traffic-mvp-v1.md), D02/B01/B06 và phần nền D03/D08.
- Mục tiêu: mô tả chính xác 12 điểm, định danh các dataset theo measurement/mode và cung cấp policy rõ ràng cho live serving trước khi triển khai sink ở P2.
- Không coi validation config hoặc report offline là evidence provider coverage/live integration.

## S01. Registry điểm cố định

Đọc `configs/sources.yaml`, giữ nguyên ID/tọa độ và 6 điểm mỗi thành phố. Contract `MonitoringPoint` dùng `point_id` nhưng nhận alias đầu vào `segment_id` của config hiện tại. Point identity không tự xác nhận provider segment hoặc physical road direction.

`load_monitoring_points(path)` trả tuple 12 điểm, từ chối duplicate, thiếu/thừa ID, thành phố sai, lat/lon ngoài range hoặc field point không hỗ trợ. Validate cấu hình RSS ở nguồn khác; phần `sources` không phải point record.

Coordinates được bảo toàn khi parse. Khi lập report, provider/network mapping có trạng thái `unverified`; không tạo tên đường, direction hay synthetic geometry để lấp chỗ trống. Weather cell lấy đúng cấu hình hiện có; nhiều điểm có thể cùng cell.

## S02. Dataset profiles

Thêm `configs/datasets.yaml` với schema version `1`, bốn profile:

| dataset_id | purpose | measurement | unit khai báo ban đầu | acquisition status |
|---|---|---|---|---|
| `vn-mvp-12` | operational | speed | km/h | configured_unverified |
| `metr-la` | benchmark | speed | mph | not_acquired |
| `ua-detrac` | benchmark | video | frame | not_acquired |
| `largest` | benchmark | flow | source_units_unverified | not_acquired |

Profile chứa source URI/reference, profile version `1` và các trường ở bảng. Acquisition status mô tả artifact được xác minh trong project, không suy từ tên dataset có trong file cấu hình. Quyền/availability được ghi `unverified` lúc chưa xác minh theo dataset cụ thể.

`load_dataset_profiles(path)` trả mapping theo ID, từ chối trùng ID, enum sai và tổ hợp measurement/unit không hợp lệ. LargeST chưa cho import flow trước khi xác minh unit/aggregation; profile chưa xác minh vẫn đọc được để mô tả research readiness.

## S03. Policy cho dữ liệu được phép phục vụ live

`may_serve_current(profile, *, mode, point_id, points)` chỉ trả True khi `profile.dataset_id == 'vn-mvp-12'`, purpose operational, measurement speed, unit km/h, mode live và point thuộc registry. Các mode chỉ gồm live, replay, reprocess; mode không hợp lệ bị từ chối bằng ValueError.

Replay/reprocess không trực tiếp cập nhật live current state trong policy này. Benchmark mode live vẫn không đủ điều kiện. P1 xuất policy và chứng minh bằng kiểm tra hành vi; việc gọi policy trong worker/sink và storage namespace được triển khai ở P2, chưa được báo là đã enforce end-to-end.

Không thêm các field vào Kafka envelope, event schema hoặc DB ngay trong P1; việc di trú hợp đồng có version và propagation thực hiện tại phase sở hữu producer/sink. Tránh làm vỡ schema hiện có bằng thay đổi nửa chừng.

## S04. Report offline có thể tái tạo

CLI `python -m cognitive_traffic.monitoring.registry_report` đọc registry và profiles, xuất JSON ra stdout. Các tùy chọn: `--sources`, `--datasets`; mặc định là hai config ở trên. Config lỗi: exit 2, stderr có lỗi validation, stdout không có report hợp lệ.

Report gồm schema_version, sources_sha256, datasets_sha256, configured_points=12, points_by_city, danh sách điểm với mapping_status=unverified, dataset profiles và live-serving eligibility theo policy. Không chứa API key/credential, thời điểm/coverage giả hoặc phát biểu dữ liệu đã được tải. Với cùng input bytes, JSON cùng nội dung và thứ tự ổn định; không thêm timestamp hiện tại phá tính xác định.

Khi vận hành sau này, acquisition/mapping verification được ghi trong evidence riêng có reference; CLI P1 chỉ báo trạng thái khai báo, chưa tự truy vấn provider. Lệnh xuất file dùng `.local/` theo quy ước repo.

## S05. Nghiệm thu riêng P1

- Đủ 12 ID và đúng tọa độ/city so với config gốc; không phát sinh thêm monitoring point.
- Duplicate/missing/extra ID, sai tọa độ/city và profile sai bị phát hiện.
- Unknown mapping và chưa tải dataset được hiển thị đúng.
- Benchmark, replay, reprocess và unknown point không đạt policy phục vụ current.
- CLI có exit behavior và digest ổn định; report không có dữ liệu nguồn hoặc quyền sử dụng được tự suy đoán.
- Các consumer hiện có vẫn sử dụng `configs/sources.yaml` bình thường; production contracts chưa bị thay đổi.

## Trách nhiệm file

| File | Trách nhiệm |
|---|---|
| `contracts/registry.py` | `MonitoringPoint`, enum, `DatasetProfile`, validation shape và measurement/unit |
| `monitoring/registry.py` | Load config, kiểm tra scope 12 điểm, `may_serve_current` |
| `monitoring/registry_report.py` | Report và CLI, không gọi source ngoài |
| `configs/datasets.yaml` | Dataset identities, purpose, measurement, trạng thái khai báo |
| `tests/unit/test_registry.py` | Scope invariant, profile validation và serving policy |
| `tests/unit/test_registry_report.py` | CLI/report determinism, lỗi config và evidence labels |

Các path Python trong bảng là tương đối với `src/cognitive_traffic/`; test/config paths tính từ root repo.
