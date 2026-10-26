# Cognitive Traffic MVP — delivery roadmap

- Ngày: 2026-10-26. Trạng thái: roadmap triển khai dựa trên hướng đã duyệt; các bước chưa được đánh dấu là hoàn thành.
- Authority: [yêu cầu MVP v1.2](../../requirements/cognitive-traffic-mvp-v1.md), [nghiên cứu ba repo](../../research/reference-repositories-review-v1.md).
- Người dùng chính: người giám sát; người đi đường sử dụng cùng nguồn dữ liệu qua so thời điểm và template tuyến.
- Scope: đúng 12 điểm hiện tại, 6 điểm mỗi thành phố. Benchmark bên ngoài có namespace/mode riêng và không tăng số điểm sản phẩm.

## Thứ tự và trace yêu cầu

| Phase | Phần bàn giao độc lập | Yêu cầu sở hữu | Gate trước phần tiếp theo |
|---|---|---|---|
| P1 | Registry 12 điểm, dataset profiles và policy ngăn benchmark đi vào live serving | D02, B01, B06; nền cho D03/D08 | Config có validation, policy có kiểm tra hành vi, report phân biệt configured với verified |
| P2 | Traffic ingestion → raw archive → canonical → PostgreSQL → API/UI current/history có quality | F01–F02, D01–D03, D06–D07, D09–D10; enforce B01 tại sink | 12 điểm luôn hiện; missing/stale/zero/closure/fetch_error đúng; retry/replay không làm sai current |
| P3 | Rule baseline, lifecycle cảnh báo, evidence trace và operator review | F03–F04, phần cảnh báo F09–F10; D06–D09 | Alert không chập chờn/nhân đôi; outage không resolve; review độc lập lifecycle |
| P4 | Notebook-first feature/baseline/model +15/+60, dataset manifest, METR-LA benchmark, artifact export và outcome | F05, phần model F09–F10; D03/D05/D08, B02, N01–N05 | Notebook chạy từ kernel sạch; temporal evaluation và target đúng; benchmark/live tách; inference load artifact và promotion có bằng chứng |
| P5 | Weather cell/RSS extraction, match, expiry và context feature/ablation | F06, D04–D05; phần context F09 | Matched/ambiguous/unmatched/expired có metrics; chỉ dùng dữ liệu khả dụng đúng thời điểm |
| P6 | So giờ tại điểm, hai template tuyến hợp lệ, coverage/ETA eligibility | F07–F08, B06 | Không suy ETA toàn tuyến từ vài anchor; nếu F08 bị chặn phải ghi rõ phần chưa đạt |
| P7 | CV spike trong notebook với video/sequence hợp lệ, count/ROI evaluation, fine-tuning nếu cần và chi phí | Mục 7 yêu cầu, B03/B05, N01–N05 khi áp dụng | Report có nhãn benchmark/local/live; model/ROI artifact có version; decision tích hợp dựa trên mapping và lợi ích thực đo |
| P8 | Replay/recovery, end-to-end evidence, walkthrough hai luồng người dùng và runbook | Hoàn thiện F09–F10, D01–D10; nghiệm thu F01–F08/B01–B06 | Capability matrix phản ánh implemented/verified/blocked/deferred, chưa đạt không bị gọi là hoàn thành |

LargeST B04 là nghiên cứu bổ sung sau speed benchmark hoặc khi có nhu cầu scale/flow; chưa là điều kiện buộc tải toàn dataset để hoàn thành P2–P6. P7 có thể khảo sát quyền/video sớm nhưng không chặn core do chưa có camera.

## Điều chỉnh workflow model theo yêu cầu notebooks

Không viết lại roadmap hoặc P1. P4 cập nhật `notebooks/exploration.ipynb` hiện có; notebook này còn import `ml.*` cũ nên phải chuyển sang `cognitive_traffic.forecasting` trước khi dùng làm evidence. Notebook thực thi audit/train/evaluate/export, package sở hữu logic dùng chung, inference load artifact độc lập.

P4 phải điều chỉnh DAG train trực tiếp hiện có để nhận/kiểm tra notebook-produced artifacts và promotion gate. Dataset preparation, DQ và replay vẫn thuộc orchestration. Việc chạy train trên notebook giữ benchmark/local runs tách namespace và không tự promote model khi chưa đạt gate.

P7 tạo `notebooks/cv_experiments.ipynb` khi có đầu vào hợp lệ. LargeST notebook riêng chỉ được tạo khi kích hoạt nghiên cứu flow/scale. Artifacts và data lớn không lưu trong notebook hoặc commit vào repo; notebook phải ghi môi trường, seed, manifest và references để tái tạo.

## Quy tắc thực thi

1. Mỗi phase có spec/plan riêng, bắt đầu bằng đọc lại code tại thời điểm thực hiện. Roadmap này không thay các implementation plan cụ thể.
2. Dùng cùng các component đang có; một worker/module mới phải có owner dữ liệu và failure mode rõ.
3. Working tree hiện chứa thay đổi cấu trúc lớn của người dùng. Trước sửa code, ghi nhận trạng thái và giữ nguyên các thay đổi không thuộc task; không tự commit toàn working tree hoặc tạo worktree làm mất context chưa commit.
4. Chạy các kiểm tra phù hợp với phần sửa. Test bằng fixtures, integration với stack thật và external source checks báo tách biệt.
5. Không cài dependency lớn/tải toàn dataset/chạy worker dài hạn chỉ để làm đẹp evidence. Metadata/rights/subset được kiểm tra trước acquisition.
6. Khi thiếu lịch sử/nguồn ngoài, hoàn thiện code path và fallback trong phạm vi được phép; ghi capability thiếu evidence, không thay bằng số liệu giả.
7. CV/ML worker học theo reference architecture nhưng không nhập code hoặc giấy phép dataset vào repo mà bỏ qua nguồn/version.

## Phần đầu đã có spec và plan chi tiết

- [P1 spec: registry và dataset boundaries](../specs/2026-10-26-registry-dataset-boundaries.md).
- [P1 implementation plan](2026-10-26-registry-dataset-boundaries.md).

P1 là một subsystem nền có thể nghiệm thu độc lập. Các yêu cầu UI, sinks, alert, model, context, routing và CV thuộc P2–P8; P1 hoàn thành không đồng nghĩa MVP hoàn thành.
