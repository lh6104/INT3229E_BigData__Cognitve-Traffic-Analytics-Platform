# Cognitive Traffic — yêu cầu MVP v1

- Ngày: 2026-10-26. Phiên bản: 1.2 — bổ sung yêu cầu thực hiện huấn luyện model trong notebooks.
- Căn cứ: người dùng chọn hướng giám sát có bằng chứng, có thêm hỗ trợ chọn thời điểm/tuyến; xác nhận giới hạn 12 điểm ở MVP và mở rộng sau.
- Mục đích: chốt yêu cầu sản phẩm, dữ liệu, phạm vi và nghiệm thu để lập kế hoạch triển khai. Đây là yêu cầu mục tiêu, chưa phải báo cáo phần đã hoàn thành.
- Tài liệu nền: [nghiên cứu và nguồn tham khảo](../research/cognitive-traffic-direction-v1.md), [kiến trúc hiện tại](../architecture.md), [cấu hình điểm](../../configs/sources.yaml).
- Phạm vi đã chốt từ người dùng: 12 điểm; người giám sát là chính; hỗ trợ di chuyển là phụ; trọng tâm Data Engineering; tránh thêm công nghệ thiếu mục đích.
- Các chính sách số ở mục 4 là mặc định thiết kế đề xuất để triển khai thử và đánh giá; chưa phải các ngưỡng có hiệu quả được chứng minh ngoài thực địa.

## 1. Mục tiêu và định nghĩa hoàn thành

Người giám sát nhìn được tình trạng 12 điểm, phân biệt ùn tắc với nguồn lỗi, kiểm tra bằng chứng cho cảnh báo, xem dự báo ngắn hạn và theo dõi kết quả. Người đi đường xem tình trạng trên template tuyến được hỗ trợ và so thời điểm đi bằng cùng dữ liệu.

“Thông minh” trong MVP thể hiện qua bốn hành vi: phát hiện khác thường so baseline; dự báo trước thay vì chỉ hiển thị số đo; trình bày bằng chứng và giới hạn; ghi outcome để đánh giá lại quyết định.

MVP đạt khi luồng dữ liệu từ nguồn đến dashboard được kiểm chứng, cảnh báo/dự báo có đánh giá ngoài mẫu với nhãn rõ ràng, và luồng tư vấn không vượt quá khả năng quan sát. Chất lượng model, chất lượng pipeline và chất lượng dữ liệu nguồn phải được báo riêng.

## 2. Phạm vi cố định: đúng 12 điểm

| Thành phố | ID điểm hiện tại |
|---|---|
| Hà Nội | `HN_HK_001`, `HN_BD_001`, `HN_CG_001`, `HN_TX_001`, `HN_RR3_001`, `HN_VNG_001` |
| TP.HCM | `HCMC_D1_001`, `HCMC_D3_001`, `HCMC_BT_001`, `HCMC_TD_001`, `HCMC_Q7_001`, `HCMC_CL_001` |

Giữ ID và tọa độ theo config. Khảo sát coverage có thể kết luận một điểm unsupported hoặc chưa match được hướng đường; điểm đó vẫn hiện trong tổng số 12. Không tự thay điểm thất bại bằng điểm mới để làm đẹp coverage.

Tách ID điểm giám sát khỏi provider segment và directed road segment. Hai điểm cùng match một provider segment không trở thành hai phép đo độc lập. Báo cả số điểm có dữ liệu trên tổng 12 và số physical segment phân biệt; chỉ số tại điểm không mô tả coverage toàn thành phố.

Weather/RSS hiện có là nguồn bối cảnh. Weather phải match theo weather cell được cấu hình, với quy tắc fallback công khai, thay vì tự dùng bất kỳ bản ghi cùng thành phố.

## 3. Yêu cầu chức năng bắt buộc

| ID | Yêu cầu | Điều kiện nghiệm thu |
|---|---|---|
| F01 | Tổng quan 12 điểm, lọc theo thành phố, bản đồ và danh sách nhất quán | Luôn thấy đủ điểm, gồm điểm chưa có số đo; thời gian cập nhật và quality state hiển thị rõ |
| F02 | Chi tiết điểm: số đo hiện tại, lịch sử, baseline, bối cảnh | Phân biệt observation với forecast; hiển thị source, đơn vị, thời điểm và thời gian thiếu dữ liệu |
| F03 | Cảnh báo hiện tại và nghi vấn bất thường | Có rule/version, lý do, input IDs, thời điểm phát hiện; gộp một sự kiện kéo dài thành một alert |
| F04 | Xác nhận, bác bỏ hoặc ghi chưa đủ bằng chứng cho cảnh báo | Kết quả review, thời điểm và người thao tác truy vết được; acknowledgment không đồng nghĩa cảnh báo đúng |
| F05 | Dự báo tại điểm ở mốc +15 và +60 phút khi đủ dữ liệu | Có prediction/target time, model hoặc baseline version, trạng thái freshness/eligibility; không điền số giả khi chưa sẵn sàng |
| F06 | Bằng chứng kết hợp traffic, weather và road event nếu match được | Truy được nguồn; sự kiện ambiguous/unmatched không tự gán vào một điểm; context không trở thành khẳng định nhân quả |
| F07 | So thời điểm tại điểm được chọn: hiện tại, +15 và +60 | Cùng mốc phát hành `t0`, hiển thị hiện trạng/dự báo và bất định; nếu thiếu dữ liệu phải trả lý do |
| F08 | So template tuyến trong phạm vi điểm hiện có | Hiển thị geometry hợp lệ, các điểm nằm trên tuyến, cảnh báo và dự báo tại điểm; nêu rõ phần chưa quan sát |
| F09 | Theo dõi chất lượng và kết quả sử dụng | Có freshness/coverage/invalid/duplicate/late metrics, outcome model và review cảnh báo |
| F10 | Replay một trường hợp để giải thích lại quyết định | Truy đúng dữ liệu/version tại thời điểm ra quyết định; kết quả reprocessing mới được phân biệt |

F04 yêu cầu ghi trạng thái qua API/dashboard, bổ sung vào API hiện chủ yếu đọc. Phạm vi là thao tác review trong môi trường MVP được kiểm soát; ghi reviewer từ danh tính thực hoặc nhãn vận hành công khai, không mặc định hệ thống đã có xác thực production.

F06 yêu cầu đường đi context hoạt động và được đánh giá, không đòi mọi RSS đều được match. Luôn có số lượng unmatched, ambiguous, expired và matched; thiếu context không đồng nghĩa không có incident.

## 4. Chính sách quan sát và cảnh báo đầu tiên

### 4.1. Thời gian và dữ liệu thiếu

- Mặc định traffic polling 300 giây theo hướng vận hành hiện tại. Một chu kỳ phải tính cả thời gian thực hiện request; lịch polling thực đo được ghi nhận.
- Observation cũ hơn hai chu kỳ traffic, mặc định 600 giây, được gắn `stale`. Đây là mặc định cấu hình; không dùng cùng ngưỡng cho weather và RSS.
- Phân biệt `observed`, `stale`, `missing`, `unsupported`, `fetch_error`. Trạng thái pipeline được giữ riêng với trạng thái giao thông gần nhất.
- Phản hồi API vừa lấy không chứng minh provider vừa đo: ghi poll time riêng và source observation time nếu nguồn có. Nếu không có source time, gắn timestamp basis là poll time.
- Dùng UTC trong lưu trữ; UI hiển thị giờ Việt Nam kèm rõ đơn vị/múi giờ ở các biểu đồ liên quan.
- Không thay missing/low confidence thành speed = 0. Số 0 hợp lệ cần giữ riêng với tình trạng không quan sát được và road closure.

### 4.2. Baseline rule minh bạch

Mặc định khởi đầu để chạy thử: tỷ lệ speed/free-flow ≤ 0.50 ở hai mẫu mới liên tiếp, quality hợp lệ và provider confidence ≥ 0.50 tạo cảnh báo tốc độ thấp. Khoảng cách hai mẫu không vượt 600 giây; mẫu trùng/late không tính là một xác nhận mới. Hai mẫu mới có tỷ lệ ≥ 0.65 cho phép đóng cảnh báo tự động. Vùng giữa hai ngưỡng giữ trạng thái để giảm chập chờn.

Đây là rule “tốc độ thấp so free-flow”, chưa phải bằng chứng “khác thường so cùng giờ/ngày”. Năng lực bất thường bổ sung baseline theo khung giờ/loại ngày khi có đủ lịch sử, được đánh giá so rule ban đầu. Ngưỡng seasonal và policy được version hóa, chọn trên train/validation rồi giữ cố định trên test.

Provider không gửi confidence thì lưu unknown; không mặc định bằng 1 để vượt điều kiện cảnh báo đã xác nhận bằng chất lượng nguồn. Có thể hiển thị tín hiệu cần kiểm tra với nhãn thiếu confidence.

Closure có bằng chứng từ nguồn hợp lệ là loại sự kiện riêng và không phải chờ rule tốc độ thấp. Khi nguồn stale/offline, giữ cảnh báo gần nhất với nhãn chưa xác minh; không tự resolved. Không khẳng định độ trễ cảnh báo tính bằng giây khi polling là năm phút; báo detection delay theo timestamp basis và cadence thực tế.

Lifecycle cảnh báo và kết quả review là hai chiều riêng. Severity mô tả mức ảnh hưởng theo policy; confidence mô tả độ chắc chắn. Cảnh báo thiếu chắc chắn vẫn có thể được ưu tiên kiểm tra nếu tác động tiềm năng lớn.

## 5. Forecast và kết hợp nguồn

1. So persistence, seasonal/historical baseline, Ridge và LightGBM bằng walk-forward trên cùng cohort. +15 là mốc chính cho cảnh báo sớm; +60 hỗ trợ so thời điểm đi. +240 nằm ngoài điều kiện nghiệm thu phiên bản này.
2. Dùng lịch sử đủ dài theo training config hiện có cho mô hình học máy: cửa sổ train tối thiểu 28 ngày, validation 7 ngày. Nếu chưa đủ, phục vụ baseline có nhãn rõ; báo forecasting nâng cao là chưa đủ bằng chứng.
3. Tách test ngoài quá trình chọn tham số và ngưỡng; báo số mẫu/fold/slice. Pinball loss trên training window không là bằng chứng calibration.
4. Weather, road event và neighbor feature phải giống nhau về định nghĩa/availability ở offline và online; feature chưa hỗ trợ hoặc thiếu dữ liệu có trạng thái rõ và chính sách xử lý missing.
5. Neighbor chỉ được dùng khi có mapping vị trí, hướng và quan hệ hợp lệ; gần nhau theo khoảng cách chưa đủ xác nhận quan hệ upstream/downstream. Không ép đủ neighbor cho cả 12 điểm.
6. Đánh giá p10–p90 bằng coverage thực nghiệm, độ rộng và pinball loss ngoài mẫu. Provider confidence, model uncertainty và source freshness là ba thông tin khác nhau.
7. Probability ùn tắc chỉ xuất hiện dưới nhãn xác suất đã hiệu chuẩn khi có kiểm chứng calibration; score suy từ ba quantile phải mang nhãn heuristic/estimated nếu chưa đạt.
8. Outcome ghép prediction với observation hợp lệ gần target time theo tolerance có version; mặc định cửa sổ ±150 giây cho cadence 300 giây. Chọn event time gần nhất; cùng khoảng cách chọn event time sớm hơn; bản ghi cùng thời điểm phải được dedup trước. Không có observation thì outcome là unavailable, chưa được coi là dự báo đúng/sai.
9. Báo hiệu quả nâng cao khi ngoài mẫu có cải thiện so baseline tốt nhất và các slice quan trọng không bị suy giảm ngoài gate cấu hình. Nếu không đạt, giữ baseline để phục vụ và công khai kết quả; không bắt buộc promote LightGBM.

## 6. Chọn thời điểm và tuyến: cam kết chính xác trong 12 điểm

### 6.1. Luồng bắt buộc của MVP

- Người dùng chọn một điểm để so hiện tại với +15/+60 tại cùng `t0`. Kết luận mô tả mức giao thông dự kiến ở điểm đó; chưa chuyển thành “đến nơi sớm hơn”.
- Có hai template tuyến cùng điểm đi–đến ở một thành phố trong phạm vi case study; chọn thành phố theo tính hợp lệ và nguồn geometry thực tế. Giữ tất cả 12 điểm trên màn hình giám sát.
- Template cần source/network version, hướng đi, vehicle mode và điểm nằm trên tuyến đã match. Mặc định case study dùng ô tô; không tự suy khả năng áp dụng cho xe máy.
- Mỗi template phải đi qua ít nhất một điểm hiện có; hai template phải có phần đường khác nhau được nhận diện. Không nối các anchor bằng đường thẳng rồi gọi đó là tuyến hợp lệ.
- Nếu không tìm được hai template hợp lệ với các điểm hiện có, ghi blocker của F08 cùng bằng chứng mapping; không thêm điểm hoặc công bố F08 hoàn thành bằng mock route.
- Thẻ tuyến hiển thị số điểm mới/tổng điểm đã map, các điểm tắc/closure, trạng thái dự báo và đoạn đường thiếu quan sát. Số điểm mới không được đổi thành phần trăm chiều dài tuyến có coverage.
- Tư vấn tại điểm và so sánh bằng chứng trên tuyến là kết quả bắt buộc. Thiếu dữ liệu để phân biệt hai tuyến phải là kết quả hợp lệ, kèm lý do dễ hiểu.

### 6.2. Gate cho ETA toàn tuyến và xếp hạng tuyến

ETA toàn tuyến là năng lực có điều kiện, không là lý do mở rộng 12 điểm trong MVP. Chỉ mở khi có toàn bộ: directed segments và chiều dài hợp lệ; mapping/hướng chính xác; policy cho mọi đoạn thiếu; bottleneck coverage; dự báo tại thời điểm tới từng đoạn; và dữ liệu hành trình để đánh giá sai số.

Mọi fallback từ historical/engine phải mang provenance riêng. Không dùng một tốc độ anchor để đại diện toàn tuyến khi chưa kiểm chứng. Không cộng quantile tốc độ từng đoạn thành quantile ETA; không gọi route nhanh nhất khi chỉ biết trạng thái vài điểm.

Nếu gate đạt, so giờ xuất phát phải báo riêng: thời gian chờ trước đi, thời gian trên đường, thời gian đến và bất định. Default objective là đến sớm nhất; ít thời gian trên đường là lựa chọn khác. Chỉ so các mốc trong horizon được đánh giá, tính cả thời điểm dự kiến tới đoạn cuối. Khi chênh lệch nhỏ hơn sai số hoặc ranking nhạy với phần thiếu, trả về chưa đủ bằng chứng để ưu tiên.

## 7. Computer vision: thử nghiệm nhỏ và có điều kiện

CV là nhánh nghiên cứu bổ sung cho MVP; phần core 12 điểm không phụ thuộc vào việc có live camera hoặc GPU. Thử nghiệm dùng một video/góc camera cố định được phép sử dụng, ưu tiên vị trí trùng một điểm nếu có thể.

Đầu ra: số xe qua vạch theo hướng và cửa sổ; số xe hiện diện trong ROI; trạng thái hàng chờ ordinal hoặc tỷ lệ track dừng. Báo model/ROI version, observation time, processing time và quality. Đánh giá với nhãn thủ công theo điều kiện quay, đặc biệt xe máy/che khuất nếu tuyên bố hỗ trợ giao thông Việt Nam.

Video benchmark khác địa điểm chỉ chứng minh nhánh CV riêng. Chỉ ghép vào forecast/alert pilot sau khi chứng minh mapping, thời gian và paired data phù hợp. Camera offline/che khuất tạo missingness; không count = 0. Speed km/h và queue length theo mét cần calibration/ground truth riêng.

Deliverable CV: báo cáo khả thi, count/queue accuracy, runtime và chi phí; kết luận tích hợp, giữ nghiên cứu riêng hoặc defer có lý do. Nếu chưa có video hợp lệ, ghi điều kiện còn thiếu và không tạo số liệu minh họa như kết quả đo.

## 8. Yêu cầu Data Engineering và vận hành

| ID | Hợp đồng bắt buộc | Evidence |
|---|---|---|
| D01 | Raw payload hoặc reference/hash theo quyền sử dụng; source ID, schema version, thời điểm, poll outcome | Truy một observation về nguồn; lỗi một điểm không chặn 11 điểm còn lại |
| D02 | Canonical observation tách measurement khỏi quality; point/provider/segment mapping có version | Mapping report cho đủ 12 điểm, gồm ambiguous/unsupported; dedup provider segment |
| D03 | `event_time`, `ingested_at`, `available_at`, source time basis và late policy nhất quán | Feature không đọc dữ liệu khả dụng sau prediction time; giữ bằng chứng first-seen trong lịch sử |
| D04 | Weather theo cell; RSS có location/time extraction, evidence và dedup | Matched/unmatched/expired metrics; thiếu source không bị hiểu là không có sự kiện |
| D05 | Snapshot/version dùng chung cho feature offline/online | So cùng input ra feature tương đương; missing-value policy không làm mất toàn bộ cohort một cách âm thầm |
| D06 | Raw/archive, feature, forecast, alert và outcome có owner persistence rõ ràng | Sự kiện đi được tới operational store và API; có xử lý retry, sink lỗi và checkpoint/recovery |
| D07 | Replay/idempotency qua Kafka, lake và PostgreSQL | Retry không nhân bản cùng kết quả; historical replay không ghi đè current mới hơn bằng sự kiện cũ |
| D08 | Dataset manifest và model/rules lineage | Dataset window/object IDs, feature/schema version, code snapshot và model/rule version truy vết được |
| D09 | Metrics và tình trạng phụ thuộc | Coverage theo điểm và theo source; invalid/late/duplicate/freshness; health không chỉ suy từ PostgreSQL |
| D10 | Bounded retention và cost | Request count, payload/video size, artifact lifecycle và compute report; quyền lưu nguồn được ghi nhận |

Không dùng active weather/RSS mapping ở hiện tại để âm thầm diễn giải lại toàn bộ lịch sử. Replay tái hiện quyết định và reprocessing bằng logic mới là hai mode có nhãn riêng.

Tận dụng stack trong repo: Kafka, Flink/Python, MinIO/S3, PostgreSQL, Airflow và MLflow. Redis dùng khi có nhu cầu đo được. Không thêm engine, database hoặc orchestration framework mới chỉ để có thêm công nghệ.

## 9. Bảng nghiệm thu và giới hạn bằng chứng

| Nhóm | Điều kiện bắt buộc | Cách báo kết quả |
|---|---|---|
| Scope | Đúng 12 ID/tọa độ, 6 điểm mỗi thành phố | Tách configured points, reporting points và unique provider segments |
| Dữ liệu lỗi | Có case missing, stale, fetch_error, zero hợp lệ, closure | Không biến outage thành thông đường; không tự resolved khi mất nguồn |
| Alert | Có nhãn event, rule baseline, review flow, hysteresis và dedup | Event precision/recall, false alarms/observed point-hour, detection delay; nói rõ điểm trùng physical segment |
| Forecast | Có ngoài mẫu, baseline comparisons, outcomes và fallback | +15/+60 báo riêng; samples/folds, MAE/bias, interval coverage; chưa đủ dữ liệu thì chưa xác nhận learned forecasting |
| Context | Có extraction/match và validity windows, đường đi feature thực sự chạy | Ablation cùng cohort; report riêng tăng coverage với cải thiện model |
| Departure | So hiện tại/+15/+60 tại điểm và cùng thời điểm phát hành | Không dùng dữ liệu tương lai trong replay; không suy thời gian đến từ point forecast |
| Route | Hai template hợp lệ hoặc blocker được ghi rõ; giao diện hỗ trợ insufficient evidence | Phân biệt point coverage với route coverage; ETA/ranking chỉ mở khi qua gate |
| E2E | Nguồn/replay raw → normalize → features → forecast/alert → PostgreSQL → API/dashboard | Lưu run ID, thời gian, code snapshot, counts và lỗi; phụ thuộc bên ngoài được xác minh riêng |
| Reproducibility | Replay và fault/retry cases có bằng chứng | Có trace end-to-end và dữ liệu/version; không gọi fixture-only là live integration |
| CV | Có report nhánh thử nghiệm hoặc lý do chưa thể chạy | Benchmark/local video/live đúng địa điểm là ba loại bằng chứng khác nhau |

Ngưỡng severity, seasonal anomaly và gate model được chọn trên train/validation, ghi trong config và khóa trước test. Ngưỡng mặc định ở mục 4 phục vụ vòng đầu; báo số đo thật thay vì khẳng định đạt một KPI chưa được thiết lập.

Một mô hình chưa thắng baseline không làm mất giá trị pipeline; phải giữ baseline và trạng thái capability đúng sự thật. Ngược lại, forecast đẹp trên fixture không chứng minh pipeline live, coverage nguồn hoặc khả năng tư vấn tuyến.

## 10. Thứ tự thực hiện sau bản yêu cầu

1. Kiểm kê và mapping 12 điểm; xác nhận nguồn, timestamps, coverage và case study tuyến bằng dữ liệu có sẵn/được phép lấy.
2. Đóng hợp đồng canonical/quality và persistence end-to-end; operational UI luôn đủ 12 điểm, gồm lỗi/missing.
3. Làm baseline giám sát, alert lifecycle/review và trace bằng chứng.
4. Hoàn thiện point-in-time feature và đánh giá forecast +15/+60; phục vụ baseline trước nếu chưa có model đủ bằng chứng.
5. Thêm context weather/RSS có match/expiry, kiểm tra parity và giá trị từng nhóm nguồn.
6. Hoàn thiện so thời điểm tại điểm và thẻ template tuyến; đánh giá gate ETA, giữ insufficient evidence khi chưa đạt.
7. Thử CV có phạm vi nhỏ, đo lợi ích/chi phí rồi quyết định tích hợp; thu thập video hợp lệ có thể bắt đầu từ bước 1.
8. Chạy nghiệm thu E2E, replay/recovery và walkthrough hai luồng người dùng; ghi rõ các capability đạt, chưa đạt và giới hạn.

Mở rộng số điểm, full-network routing, ETA không có ground truth, tracking đa camera, nhận diện biển số, GNN/Transformer, tự điều khiển đèn và chatbot nằm ngoài MVP v1.

## 11. Các artifact cần bàn giao khi triển khai

- Bảng mapping/coverage 12 điểm; source-use register; template tuyến với vehicle/network version.
- Hợp đồng dữ liệu và config rule/quality/model; migrations và worker/API/UI đáp ứng F01–F10.
- Dataset/evaluation manifest; baseline/forecast/context report; CV feasibility report nếu đủ đầu vào.
- Evidence E2E và replay/recovery gắn code snapshot/run ID; danh sách capability và lỗi còn mở.
- Hướng dẫn chạy MVP, giới hạn nguồn/độ phủ và kịch bản demo cho người giám sát và người đi đường.

Nếu F08 hoặc learned forecast chưa đạt điều kiện dữ liệu, phiên bản bàn giao phải ghi nhận rõ phần chưa đạt; không đổi yêu cầu thành hoàn thành chỉ bằng một thông báo fallback. Spec/implementation plan tiếp theo phải trace từng hạng mục về ID yêu cầu trong tài liệu này.

## 12. Quyết định đã duyệt sau nghiên cứu ba repo

Căn cứ: [báo cáo đối chiếu repo](../research/reference-repositories-review-v1.md) và phản hồi “duyệt” của người dùng. Các quyết định này bổ sung yêu cầu dữ liệu/kiến trúc, giữ phạm vi sản phẩm ở 12 điểm.

| ID | Quyết định | Điều kiện nghiệm thu |
|---|---|---|
| B01 | Tách dataset benchmark khỏi dữ liệu vận hành | Dataset ID, measurement, mode live/replay và source identity theo được tới manifest/model/outcome; benchmark không ghi current state hoặc metrics của 12 điểm Việt Nam |
| B02 | METR-LA là dataset speed benchmark đầu tiên | Subset, unit, timezone/timestamp basis, split và target +15/+60 được xác minh; báo riêng kết quả benchmark và kết quả địa phương |
| B03 | UA-DETRAC dùng cho CV spike có giới hạn | Giữ sequence split và observation time; đo count theo ROI/line crossing; chỉ tích hợp pilot khi có mapping/paired data phù hợp |
| B04 | LargeST là dataset flow/scale có điều kiện | Schema/unit/aggregation/missing mask riêng; quyền sử dụng được ghi nhận; không đổi flow thành speed để đưa vào training |
| B05 | Học cách tách worker inference khỏi stream engine | CV/ML inference nặng và artifact I/O tách khỏi feature job; retry, idempotency và state recovery có policy và evidence |
| B06 | Tách sensor graph khỏi road graph | Neighbor/impact graph không được coi là mạng định tuyến; ETA/routing tiếp tục tuân theo gate ở mục 6.2 |

NYC TLC chưa có bài toán cần đưa vào MVP. Giữ stack hiện tại; ONNX, Spark/Delta, GNN hoặc routing engine mới chỉ được xem xét khi có yêu cầu/đo đạc cụ thể. Nhập dữ liệu công khai không tự chứng minh multimodal fusion có hiệu quả.

Kế hoạch tổng thể và trace yêu cầu: [MVP delivery roadmap](../superpowers/plans/2026-10-26-cognitive-traffic-mvp-roadmap.md). Subsystem đầu tiên: [registry và ranh giới dataset](../superpowers/specs/2026-10-26-registry-dataset-boundaries.md).

## 13. Huấn luyện và đánh giá model trong notebooks

Người dùng yêu cầu phần cần train model được thực hiện trong `notebooks/`. Quy tắc này áp dụng cho forecasting, speed benchmark và CV fine-tuning nếu thử nghiệm cho thấy cần thiết; không tạo một workflow train độc lập khác trong MVP.

| ID | Yêu cầu | Điều kiện nghiệm thu |
|---|---|---|
| N01 | Notebook là điểm thực thi huấn luyện, đánh giá và chọn candidate model | Chạy lại từ kernel sạch theo thứ tự cell; tham số dataset, split, seed và horizon được khai báo đầu notebook |
| N02 | Notebook tái sử dụng logic package | Import feature/target/split/evaluation/training/artifact helpers từ `src/cognitive_traffic`; không nhân bản logic feature khác với inference |
| N03 | Forecast notebook phân biệt local MVP và benchmark | Một lần chạy chọn một dataset namespace; horizon +15/+60, target time và temporal split rõ; không dùng benchmark model làm champion Việt Nam khi chưa có local evaluation |
| N04 | Notebook xuất artifact độc lập để phục vụ | Bundle, feature order/schema/version, preprocessing, dataset/split manifest, metrics theo horizon/fold và run/environment metadata; inference không phụ thuộc notebook kernel |
| N05 | Notebook là nguồn evidence có thể tái tạo | Báo baseline/out-of-sample metrics, calibration và missingness; artifact có checksum/reference; không coi cell output cũ là kết quả đã chạy trên code/data hiện tại |

### Phân công notebook

- `notebooks/exploration.ipynb`: cập nhật notebook hiện có thành workflow dataset audit → baseline → forecasting +15/+60 → evaluation → export. Cấu hình dataset cho phép local MVP hoặc METR-LA trong các run tách biệt.
- `notebooks/cv_experiments.ipynb`: tạo ở P7 nếu có video hợp lệ; kiểm tra pretrained detector/tracker/count trước, chỉ fine-tune khi có lý do và split/nhãn đủ. Giữ đánh giá theo sequence/camera.
- `notebooks/largest_flow_benchmark.ipynb`: chỉ tạo khi kích hoạt nghiên cứu LargeST B04; target flow và đơn vị được xác minh riêng.

Notebook hiện có còn import `ml.training.*`/`ml.tracking.*` và ghi artifact theo layout cũ; P4 cần chuyển sang package hiện tại. Đây là yêu cầu cần thực hiện, chưa là xác nhận notebook đang chạy được.

Artifact local ghi `.local/`; trên Kaggle dùng `/kaggle/working`; artifact bàn giao có thể upload MinIO/MLflow. Không commit model binaries hoặc credential vào notebook/repo. Inference worker chỉ load artifact đã được đánh giá theo gate.

Airflow phục vụ dataset preparation, DQ/replay và kiểm tra artifact/gate. DAG `orchestration/dags/train_forecast.py` hiện gọi train trực tiếp; P4 cần điều chỉnh lifecycle này theo notebook-produced artifacts để tránh hai quy trình train khác nhau. Không tự chạy hoặc sửa DAG ở bước cập nhật yêu cầu này.

P1 registry/dataset boundaries giữ nguyên. Không cần viết lại toàn roadmap; spec/implementation plan chi tiết P4 và P7 phải bao gồm N01–N05 khi đến phase tương ứng.
