# Cognitive Traffic — MVP requirements v1

Date: 2026-10-26. Version: **1.3**, canonical English edition of v1.2. This specification records approved target behavior; it is not a completion report. The user selected evidence-based operator monitoring, secondary departure/route support, exactly 12 points before future expansion, and a Data Engineering focus. Numeric policies below are initial configurable design defaults for evaluation, not field-proven thresholds.

Read the [research direction](../research/cognitive-traffic-direction-v1.md), [reference review](../research/reference-repositories-review-v1.md), [architecture](../architecture.md), [point configuration](../../configs/sources.yaml), [task tracker](../tasks/tracker.md) and [verification ledger](../evidence/rubric-validation.md). The complete historical Vietnamese edition remains in Git at revision `43ac84e62ec06a0a92429d1db5d87ca056f6b804`; this English edition is authoritative for assessment.

## 1. Objective and definition of done

Operators must see the state of all 12 points, distinguish congestion from source failure, inspect alert evidence, view short-horizon forecasts and track outcomes. Travelers use the same data to inspect supported route templates and compare departure times.

“Cognitive” means four measurable behaviors: detect departures from a baseline; forecast rather than merely display measurements; show evidence and limitations; record outcomes to evaluate decisions. Completion requires a verified source-to-dashboard path, explicitly labelled out-of-sample alert/forecast evaluation, and advice bounded by actual observability. Report model quality, pipeline quality and source quality separately.

## 2. Fixed scope: exactly 12 points

| City | Existing point IDs |
|---|---|
| Hanoi | `HN_HK_001`, `HN_BD_001`, `HN_CG_001`, `HN_TX_001`, `HN_RR3_001`, `HN_VNG_001` |
| Ho Chi Minh City | `HCMC_D1_001`, `HCMC_D3_001`, `HCMC_BT_001`, `HCMC_TD_001`, `HCMC_Q7_001`, `HCMC_CL_001` |

Preserve configured IDs and coordinates. An unsupported or direction-unmatched point remains among the 12; do not replace failed points to improve apparent coverage. Separate monitoring-point identity, provider segment and directed physical road segment. Two anchors matching one provider segment are not independent measurements. Report reporting-points/12 and unique physical segments; point coverage does not describe citywide coverage.

Weather/RSS are context sources. Match weather by configured weather cell and explicit fallback policy; do not silently substitute any record from the same city.

## 3. Mandatory functional requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| F01 | Twelve-point overview with city filter, consistent map/list | All points remain visible, including unobserved points; update time and quality state are explicit |
| F02 | Point detail: current measurement, history, baseline and context | Distinguish observation/forecast; show source, units, timestamps and missing-data intervals |
| F03 | Current alerts and suspected anomalies | Rule/version, reason, input IDs and detection time; merge sustained signals into one alert |
| F04 | Confirm, reject or mark insufficient evidence for an alert | Trace reviewer/action time/outcome; acknowledgment does not mean the alert is correct |
| F05 | Point forecasts at +15/+60 minutes when eligible | Prediction/target time, model or baseline version, freshness/eligibility; no invented values when unavailable |
| F06 | Combined traffic/weather/road-event evidence when matched | Trace sources; ambiguous/unmatched events are not assigned automatically; context is not a causal claim |
| F07 | Compare now/+15/+60 at a selected point | Same issue time `t0`, explicit observed/predicted state and uncertainty; explain unavailable data |
| F08 | Compare route templates within existing point scope | Valid geometry, matched points, alerts and point forecasts; identify unobserved road sections |
| F09 | Track data quality and usage outcomes | Freshness/coverage/invalid/duplicate/late metrics, model outcomes and alert reviews |
| F10 | Replay a case to explain its decision | Recover the actual data/version known then; distinguish new reprocessing results |

F04 requires a write path in the controlled MVP API/dashboard. Record a real identity or an explicit operator label; do not imply production authentication exists. F06 requires a working, evaluated context path, not successful matching of every RSS item. Report unmatched, ambiguous, expired and matched counts. Missing context does not mean no incident occurred.

## 4. Initial observation and alert policies

### 4.1 Time and missing data

Traffic polling defaults to 300 seconds. Include request execution time in the actual observed cadence. Traffic observations older than two cycles (default 600 seconds) become `stale`; weather/RSS use their own thresholds. Distinguish `observed`, `stale`, `missing`, `unsupported` and `fetch_error`. Keep pipeline state separate from the most recent traffic state.

A newly fetched API response does not establish a newly measured observation. Store poll time separately from source observation time; if unavailable, label timestamp basis as poll time. Persist UTC; show Vietnam time and explicit timezone/units on relevant charts. Missing or low-confidence data must not become speed zero. Preserve genuine observed zero separately from missingness and road closure.

### 4.2 Transparent baseline rule

Initial low-speed rule: speed/free-flow ratio ≤0.50 for two fresh consecutive observations, valid quality and provider confidence ≥0.50. Their gap must not exceed 600 seconds; duplicate/late samples do not count as a new confirmation. Two fresh samples with ratio ≥0.65 allow automatic resolution. Between thresholds retain state to avoid flapping.

This detects low speed relative to free flow; it is not yet a same-hour/day anomaly detector. Add seasonal/day-type baselines when sufficient history exists and compare against this initial rule. Version seasonal thresholds and policies; select on train/validation and freeze before test.

Missing provider confidence remains unknown, never silently 1. A provisional signal may be shown with a missing-confidence label. Source-confirmed closure is a separate event type and need not wait for the low-speed rule. On stale/offline sources retain the last alert as unverified; do not auto-resolve. With five-minute polling do not promise second-level detection: report delay using actual cadence and timestamp basis.

Alert lifecycle and review outcome are independent dimensions. Severity describes policy-based impact; confidence describes certainty. Potentially severe uncertain alerts may still deserve operator attention.

## 5. Forecasting and source fusion

1. Compare persistence, seasonal/historical medians, Ridge and LightGBM using walk-forward evaluation on the same cohort. +15 is primary for early warning; +60 supports departure comparisons. +240 is outside acceptance for this version, even if generic package configuration supports it.
2. Learned forecasting uses the configured minimum 28-day train and 7-day validation windows. With insufficient history serve an explicitly labelled baseline and mark advanced forecasting unproven.
3. Hold out test data from parameter/threshold selection. Report samples, folds and slices. Pinball loss on the final training window does not establish calibration.
4. Weather, road events and neighbor features must share offline/online definitions and availability. Unsupported/missing features need explicit state and handling policy.
5. Neighbors require verified location, direction and relationships. Geographic proximity alone does not establish upstream/downstream; do not force neighbors for every point.
6. Evaluate p10–p90 using out-of-sample empirical coverage, interval width and pinball loss. Provider confidence, model uncertainty and source freshness are distinct.
7. Label congestion probability calibrated only after calibration validation. A score inferred from three quantiles remains heuristic/estimated otherwise.
8. Match a prediction to a valid observation near target time using a versioned tolerance, initially ±150 seconds for 300-second cadence. Select nearest event time; on equal distance choose earlier event time; deduplicate identical times first. No observation means unavailable outcome, not success/failure.
9. Claim improvement only after useful out-of-sample gain against the best baseline with important slices within configured regression gates. Otherwise retain the baseline and publish the result. LightGBM promotion is not mandatory.

## 6. Departure and route advice within 12 points

### 6.1 Mandatory MVP experience

Compare now/+15/+60 for one point at common `t0`. The conclusion describes expected traffic at that point; it does not establish earlier arrival. Provide two templates with the same origin/destination in one case-study city, selected by valid real geometry. All 12 monitoring points remain visible.

Each template records source/network version, direction, vehicle mode and matched points. Start with cars; do not infer motorcycle applicability. Each passes at least one existing point and has identifiable differing road sections. Straight lines connecting anchors are not valid routes. If two valid templates cannot be found within the current points, record the F08 blocker with mapping evidence; do not add points or claim completion using mock routes.

Route cards show fresh/total matched points, congested/closed points, forecast state and unobserved sections. Fresh-point count is not length-based route coverage. Point advice and route evidence comparison are mandatory. Insufficient evidence to distinguish routes is a valid result with a clear explanation; it does not alone satisfy all route delivery requirements.

### 6.2 Gate for full-route ETA and ranking

Full-route ETA is conditional and does not justify expanding the 12-point scope. Require all: valid directed segments/lengths; accurate mapping/direction; a policy for every unobserved section; bottleneck coverage; predictions at expected segment-entry time; journey ground truth for error evaluation.

Historical/engine fallbacks retain their own provenance. Do not extrapolate one anchor speed across an unvalidated route. Do not sum segment speed quantiles into ETA quantiles. Do not claim fastest route from a few observed points.

Once eligible, departure comparison separately shows predeparture wait, travel time, arrival time and uncertainty. Earliest arrival is the default objective; least time on the road is another objective. Compare only evaluated horizons, including predicted entry to the last segment. If differences are smaller than error or ranking depends on missing-section assumptions, return insufficient evidence to prefer one option.

## 7. Computer vision: small conditional experiment

CV is supplementary research; the 12-point core must not depend on a live camera/GPU. Use one permitted fixed-view video, preferably colocated with a point. Outputs: directional line-crossing counts per window; ROI occupancy count; ordinal queue state or stationary-track fraction. Record model/ROI version, observation/processing time and quality. Evaluate manually labelled footage under claimed conditions, especially motorcycles and occlusion for Vietnamese traffic.

A different-location benchmark proves only the standalone CV path. Integrate with forecasting/alerts only after location/time mapping and paired-data validation. Offline/occluded camera creates missingness, not zero count. Speed km/h and queue length in meters require separate calibration/ground truth.

Deliver feasibility, count/queue accuracy, runtime and cost report, then decide integrate, retain as research or defer with reasons. Without lawful video, document the missing input; never present illustrative values as measured results.

## 8. Data Engineering and operations requirements

| ID | Mandatory contract | Acceptance evidence |
|---|---|---|
| D01 | Raw payload or rights-permitted reference/hash; source ID, schema, time and poll outcome | Trace an observation to source; failure at one point does not block the other 11 |
| D02 | Canonical observation separates measurement/quality; version point/provider/segment mapping | All-12 mapping report includes ambiguous/unsupported points; deduplicate provider segments |
| D03 | Consistent event/ingestion/availability time, source-time basis and lateness policy | Features exclude data available after prediction time; preserve historical first-seen evidence |
| D04 | Cell-matched weather; RSS location/time extraction, evidence and dedup | Matched/unmatched/expired metrics; missing source does not mean no event |
| D05 | Shared versioned offline/online feature snapshot | Equivalent features from the same inputs; missing handling does not silently remove the whole cohort |
| D06 | Explicit persistence owners for raw/archive, features, forecasts, alerts and outcomes | Events reach operational store/API; retry, sink failure, checkpoint and recovery are handled |
| D07 | Replay/idempotency across Kafka, lake and PostgreSQL | Retry does not duplicate results; old replay does not overwrite newer current state |
| D08 | Dataset manifests and model/rule lineage | Dataset window/object IDs, feature/schema/code snapshot and model/rule version are traceable |
| D09 | Metrics and dependency status | Point/source coverage; invalid/late/duplicate/freshness; health is more than PostgreSQL availability |
| D10 | Bounded retention and cost | Requests, payload/video size, artifact lifecycle and compute report; record source-storage rights |

Do not silently apply today's weather/RSS mappings to all historical data. Decision reproduction and new-logic reprocessing are separately labelled modes. Reuse Kafka, Flink/Python, MinIO/S3, PostgreSQL, Airflow and MLflow. Redis requires measurable need; do not add engines/databases/orchestrators merely for breadth.

## 9. Acceptance matrix and evidence boundaries

| Group | Mandatory acceptance | Reporting requirements |
|---|---|---|
| Scope | Exactly configured 12 IDs/coordinates, six per city | Separate configured points, reporting points and unique provider segments |
| Bad data | Missing, stale, fetch_error, valid zero and closure cases | Outage is not clear traffic; missing source never auto-resolves alerts |
| Alert | Event labels, baseline, review, hysteresis and dedup | Event precision/recall, false alarms per observed point-hour, detection delay; identify shared physical segments |
| Forecast | Out-of-sample baseline comparisons, outcomes and fallback | Separate +15/+60 samples/folds, MAE/bias, coverage; insufficient history leaves learned capability unverified |
| Context | Extraction/matching, validity windows and executed feature path | Same-cohort ablation; separate added coverage from model improvement |
| Departure | Now/+15/+60 at the point and same issue time | No future data in replay; no arrival-time inference from point forecasts |
| Route | Two valid templates or explicit blocker; insufficient-evidence UI | Distinguish point/route coverage; gate ETA and ranking |
| E2E | Source/replay raw→normalize→features→forecast/alert→PostgreSQL→API/dashboard | Run ID, timestamp, code snapshot, counts/errors; verify external dependencies separately |
| Reproducibility | Replay and fault/retry evidence | End-to-end trace/data/version; fixtures alone are not live integration |
| CV | Experiment report or reason it could not run | Distinguish foreign benchmark, local video and live colocated evidence |

Select severity/seasonal/model gates on train/validation, persist in config and lock before test. Report measurements rather than an unestablished KPI. A model that loses to baseline does not invalidate the pipeline, but a convincing fixture forecast proves neither live pipeline nor provider coverage/route advice.

## 10. Delivery order and exclusions

1. Inventory/map all 12 points; confirm source, timestamps, coverage and route case study using permitted data.
2. Close canonical/quality contracts and end-to-end persistence; show all points and missing/error states.
3. Deliver monitoring baseline, alert lifecycle/review and evidence trace.
4. Build point-in-time features and +15/+60 evaluation; serve a baseline until a learned model has evidence.
5. Add matched/expiring weather/RSS; evaluate parity and source-group value.
6. Deliver point departure comparisons and template cards; assess ETA eligibility and retain insufficient-evidence behavior.
7. Run a bounded CV experiment and measure benefit/cost; lawful-video discovery may start at step 1.
8. Execute E2E, replay/recovery and both user walkthroughs; report achieved, incomplete and limited capabilities.

Out of scope: more points, full-network routing, ground-truth-free ETA, multicamera tracking, plate recognition, GNN/Transformer, automatic signal control and chatbots.

## 11. Required delivery artifacts

Provide all-12 mapping/coverage matrix, source-use register and vehicle/network-versioned templates; contracts/config/rules/quality/model gates, migrations and F01–F10 worker/API/UI; dataset/evaluation manifests and baseline/forecast/context reports; CV feasibility report if inputs permit; code/run-linked E2E/replay/recovery evidence and capability/open-defect register; run instructions, coverage limits and both-user demo scripts.

If F08 or learned forecasting lacks data prerequisites, explicitly record it incomplete. A fallback message does not turn an unmet requirement into completed work. Every scoped spec/plan traces to these requirement IDs.

## 12. Approved decisions from reference-repository research

The user approved [the three-repository review](../research/reference-repositories-review-v1.md). These decisions supplement data/architecture requirements while preserving 12-point product scope.

| ID | Approved decision | Acceptance criteria |
|---|---|---|
| B01 | Separate benchmark/operational datasets | Dataset ID, measurement, mode and source identity reach manifest/model/outcome; benchmarks never update Vietnamese live state or metrics |
| B02 | METR-LA is the first speed benchmark | Verify subset, units, timezone/timestamp basis, splits and +15/+60 targets; label benchmark/local results separately |
| B03 | Bounded UA-DETRAC CV spike | Preserve sequence split/observation time; ROI/line-crossing evaluation; pilot integration requires valid mapping/paired data |
| B04 | LargeST is conditional flow/scale research | Separate schema/unit/aggregation/missing mask and documented rights; never rename flow to speed |
| B05 | Separate inference workers from stream engine | Heavy CV/ML and artifact I/O stay outside feature job; retry/idempotency/state recovery have policy/evidence |
| B06 | Separate sensor graph from road graph | Neighbor/impact graph is not a routing network; ETA/routing still obey section 6.2 |

NYC TLC has no current MVP requirement. Consider ONNX, Spark/Delta, GNN or a new routing engine only for a concrete measured need. Public-dataset ingestion does not prove multimodal fusion improves results. See [roadmap](../superpowers/plans/2026-10-26-cognitive-traffic-mvp-roadmap.md) and [P1 specification](../superpowers/specs/2026-10-26-registry-dataset-boundaries.md).

## 13. Notebook-first training and evaluation

The user requires all model-training execution in `notebooks/`: forecasting, speed benchmark and CV fine-tuning when justified. Do not introduce another independent training workflow.

| ID | Requirement | Acceptance criteria |
|---|---|---|
| N01 | Notebook executes training, evaluation and candidate selection | Clean-kernel sequential execution; dataset/split/seed/horizons declared first |
| N02 | Notebook reuses package logic | Import feature/target/split/evaluation/training/artifact helpers from `src/cognitive_traffic`; do not duplicate inference feature logic |
| N03 | Separate local MVP/benchmark runs | One namespace per run, +15/+60 targets and temporal split explicit; benchmark model is not Vietnamese champion without local evaluation |
| N04 | Export independent serving artifact | Bundle, feature order/schema/version, preprocessing, dataset/split manifest, per-horizon/fold metrics, run/environment metadata; inference independent of kernel |
| N05 | Notebook is reproducible evidence | Baseline/out-of-sample/calibration/missingness reports and checksum/reference; stale cell outputs are not evidence on current code/data |

`notebooks/exploration.ipynb` owns dataset audit→baseline→+15/+60 forecasting→evaluation→export, with separate local/METR-LA runs. Create `notebooks/cv_experiments.ipynb` in P7 only with lawful video: test pretrained detector/tracker/count first; fine-tune only with justified need and sufficient sequence/camera-level labels/splits. Create `notebooks/largest_flow_benchmark.ipynb` only when B04 activates, with independently verified flow target/units.

The old notebook's removed `ml.*` imports and artifact layout must be migrated before use as evidence. Write local artifacts under `.local/`, Kaggle artifacts under `/kaggle/working`; handoff may upload to MinIO/MLflow. Do not commit model binaries, large data or credentials. Inference loads only evaluated eligible artifacts.

Airflow handles dataset preparation, DQ/replay and artifact/gate validation. `orchestration/dags/train_forecast.py` must accept notebook-produced candidates and measured checks, never execute a second training path or infer a passed gate from constants. P1 remains unchanged; detailed P4/P7 plans must include N01–N05.
