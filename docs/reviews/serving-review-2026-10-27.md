# Serving review and scoped corrections — 2026-10-27

Scope: independent read-only inspection of registry bootstrap, sink eligibility, transactional persistence, consumer acknowledgments and map missing-state semantics, followed by controller-authorized fixes to the two findings below. This is an agent review, not a qualifying human/course peer review.

| Severity | Finding | Correction and regression evidence |
|---|---|---|
| P1 | Bootstrap parsed raw YAML and checked only twelve unique IDs. Unapproved identity, wrong city and out-of-range coordinates bypassed the canonical registry contract and could become monitored/sink-eligible. | `storage/bootstrap.py` now calls `load_monitoring_points` before database changes, retains advisory-lock/transactional migrations, and seeds validated objects. Four invalid-config tests failed before the fix; all five bootstrap tests pass afterward. |
| P2 | `/traffic/current` read all stored current rows, including a disabled prior road or ineligible existing-volume provenance. New `/monitoring/points` already filtered correctly. | `storage/postgres.py` now filters enabled monitoring points and operational/vn-mvp-12 identity. Real PostgreSQL regression failed before the fix; disabled road, replay mode, benchmark/unknown dataset now remain absent while history is preserved. |

Checks executed in the existing `traffic` environment:

```bash
conda run --no-capture-output -n traffic python -m pytest \
  tests/integration/test_serving_persistence.py \
  tests/unit/test_bootstrap.py tests/forecasting/test_candidate_review.py -q
conda run --no-capture-output -n traffic python -m ruff check \
  src/cognitive_traffic/storage/bootstrap.py src/cognitive_traffic/storage/postgres.py \
  tests/unit/test_bootstrap.py tests/forecasting/test_candidate_review.py \
  tests/integration/test_serving_persistence.py
git diff --check
```

Result: **48 tests passed**, Ruff passed, whitespace check passed. The pytest process received `TRAFFIC_TEST_DSN` pointing to dedicated temporary `postgres:16-alpine` container `cognitive-docs-review-b3dc53dd`, ephemeral loopback port 46171. Each PostgreSQL fixture used its own random schema. The dedicated container was removed after verification; no application/ADG containers or persistent volumes were changed. The test count comprises 13 real PostgreSQL cases, five bootstrap unit cases and 30 candidate/notebook component cases. This is not a Kafka/browser smoke or full Airflow integration run.

Source inspection also found the history/current transaction atomic under the psycopg connection context, payload-matching duplicates handled without new history, collision errors rolling back, monotonic current updates, and database exceptions escaping before the synchronous Kafka offset commit. Existing tests cover crash rollback, duplicate delivery, concurrency, older events, replay/benchmark/future rejection and stale reads. Broader smoke/recovery results belong in the integration validation ledger.

Known product-quality gaps remain: provider-absent confidence currently becomes 1.0; provider closure/source-state distinctions are not fully represented in the canonical observation/read UI; fetch errors do not yet produce per-point `fetch_error`/`unsupported` state. These are not fixed or certified by this review. The dashboard's live/stale/missing source path and a passing local stack do not complete all P2/F01–F02 quality semantics or the full F03–F10 product. Lawful provider rights, direction/coverage mapping and local learned-model quality remain external/data-dependent gates.
