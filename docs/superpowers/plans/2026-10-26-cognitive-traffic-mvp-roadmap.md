# Cognitive Traffic MVP — delivery roadmap

Date: 2026-10-26. Status: approved-direction delivery roadmap; phases are not marked complete by this document. Authority: [MVP requirements](../../requirements/cognitive-traffic-mvp-v1.md), [reference research](../../research/reference-repositories-review-v1.md). Operators are primary; travelers reuse observations/forecasts for departure/template comparisons. Exactly 12 existing points, six per city. External benchmarks have separate dataset/mode namespaces and do not increase product point count.

## Delivery order and requirement trace

| Phase | Independently deliverable subsystem | Requirements | Gate before proceeding |
|---|---|---|---|
| P1 | Twelve-point registry, profiles and benchmark/live policy | D02, B01, B06; D03/D08 foundation | Validated configs, behavioral policy tests; configured versus verified report |
| P2 | Traffic ingestion→archive→canonical→PostgreSQL→current/history API/UI with quality | F01–F02, D01–D03, D06–D07, D09–D10; sink enforcement B01 | All points visible; correct missing/stale/zero/closure/fetch_error; retry/replay preserve current |
| P3 | Baseline rules, alert lifecycle, evidence and operator review | F03–F04, alert F09–F10; D06–D09 | No duplicate/flapping alerts; outage does not resolve; review independent of lifecycle |
| P4 | Notebook-first features/baselines/+15/+60 models, manifests, METR-LA, export/outcomes | F05, model F09–F10; D03/D05/D08, B02, N01–N05 | Clean-kernel execution; correct temporal target/evaluation; isolated benchmark; independent inference and evidenced promotion |
| P5 | Weather cells/RSS extraction, matching/expiry, context features/ablation | F06, D04–D05, context F09 | Matched/ambiguous/unmatched/expired metrics; only data available at prediction time |
| P6 | Point departure comparisons, two valid route templates, coverage/ETA eligibility | F07–F08, B06 | No full-route ETA from a few anchors; F08 blocker explicitly records unmet scope |
| P7 | Notebook CV spike with permitted video, count/ROI evaluation, justified fine-tuning/cost | Section 7, B03/B05, applicable N01–N05 | Label benchmark/local/live; version model/ROI artifact; measured mapping/benefit supports integration |
| P8 | Replay/recovery, E2E evidence, both user walkthroughs/runbook | F09–F10, D01–D10; F01–F08/B01–B06 acceptance | Capability matrix distinguishes implemented/verified/blocked/deferred; no incomplete capability called complete |

LargeST B04 is optional after speed benchmarking or on demonstrated flow/scale need; downloading it is not required for P2–P6. P7 rights/video discovery may start early without blocking the core for missing cameras.

## Notebook model workflow

P1 remains unchanged. P4 updates the existing `notebooks/exploration.ipynb` from removed `ml.*` imports to current `cognitive_traffic.forecasting`. Notebook executes audit/train/evaluate/export; package owns shared logic; inference loads an independent artifact.

P4 must replace direct DAG training with notebook-artifact validation and measured promotion checks. Dataset preparation, DQ and replay remain orchestrated. Benchmark/local runs stay separate and no model is automatically promoted without evidence.

P7 creates `notebooks/cv_experiments.ipynb` only with valid inputs. A separate LargeST notebook is conditional on B04 activation. Do not embed large data/artifacts in notebook/repository. Record environment, seed, manifest and references.

## Execution rules

1. Each phase has its own scoped spec/plan and rereads current code. This roadmap does not replace implementation plans.
2. Reuse components. Every new worker/module needs a persistence owner and concrete failure mode.
3. Preserve unrelated working-tree changes. Record status before editing; do not commit the whole tree or create an isolated checkout that loses required uncommitted context.
4. Run relevant checks; separately report fixtures, real-stack integration and external-source verification.
5. Do not install heavy dependencies, download full datasets or run long-lived workers merely to improve evidence. Check metadata/rights/subsets before acquisition.
6. When history/external sources are unavailable, implement authorized paths and fallback; report unverified capability without synthetic results presented as real.
7. Learn CV/ML boundaries from references; do not import code or dataset licensing assumptions without source/version checks.

## P1 detailed artifacts

- [Registry/dataset specification](../specs/2026-10-26-registry-dataset-boundaries.md).
- [P1 implementation plan and historical checkpoint](2026-10-26-registry-dataset-boundaries.md).

P1 is independently acceptable; its completion does not complete P2–P8 or the MVP. Current infrastructure readiness is tracked in the [task tracker](../../tasks/tracker.md) and [validation ledger](../../evidence/rubric-validation.md). Historical original: revision `43ac84e62ec06a0a92429d1db5d87ca056f6b804`.
