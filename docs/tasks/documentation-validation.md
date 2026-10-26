# Documentation and notebook-boundary validation

Date: 2026-10-26. Scope: documentation/model-boundary work package on the local working tree; no commit, push, source acquisition, training run or external message was performed.

Executed checks:

- Parsed every notebook code cell and `orchestration/dags/train_forecast.py` with Python AST. Removed `ml.*` imports; all code cells have empty outputs and execution count null.
- Parsed `.github/ISSUE_TEMPLATE/feature.yml` with PyYAML; required fields and hierarchy are present.
- Ran `conda run -n traffic python -m ruff check orchestration/dags/train_forecast.py`: passed.
- Imported the current notebook's shared training/evaluation/baseline interfaces in the existing `traffic` environment: passed. Installed metadata: cognitive-traffic 0.3.0, pandas 2.3.3, numpy 2.4.6, lightgbm 4.7.0, scikit-learn 1.6.1, joblib 1.5.3. This is one environment snapshot, not clean-install evidence.
- Ran `/tmp/check_notebook_lifecycle.py` in that environment: an extracted DAG review function with a fake object store accepted a valid controlled fixture without changing an alias; rejected benchmark namespace, non-notebook origin, unbound evidence, artifact corruption, missing gates, a truthy string instead of boolean, nonfinite metric and losing-to-baseline candidate. Eight rejection cases passed. This harness is component validation, not an Airflow scheduler or live object-store integration run.
- Scanned canonical requirements/research/specification/previous plans for remaining Vietnamese prose: none found. Historical checkpoints are explicitly historical.
- Checked local Markdown links: all existing targets resolve except the integration-owned `docs/evidence/rubric-validation.md` pending controller creation at the time of this check. Final integration must rerun link validation after that ledger exists.

Unverified: clean-kernel notebook training on lawful acquired data, upstream feature/label leakage, measured model improvement/calibration, Airflow deployment, object-store artifact upload, human peer reviews and public publication. Report references supplied to the review DAG are auditable declarations, not independent proof that checks actually ran. No automatic champion promotion occurs.

2026-10-27 continuation: preserved the lifecycle harness as `tests/forecasting/test_candidate_review.py`. Ran `conda run --no-capture-output -n traffic python -m pytest tests/forecasting/test_candidate_review.py -q`: 30 passed, exit 0. Scoped Ruff passed. These include checksum/evidence/policy/metric rejection, no-training/no-promotion assertions and notebook metadata/AST/empty-output regression. No Airflow installation or dataset training is performed. `nbformat` is unavailable in the existing host environments; notebook JSON/code AST checks do not imply a full nbformat-library validation or clean-kernel training run.

2026-10-27 serving follow-up: controller authorized the registry bootstrap and existing-volume current-read corrections discovered during independent review. [Review evidence](../reviews/serving-review-2026-10-27.md) records red→green tests and the dedicated real PostgreSQL fixture. Combined targeted suite: 48 passed (13 real PostgreSQL, five bootstrap unit, 30 candidate/notebook component), scoped Ruff and whitespace checks passed. Broader source-quality semantics remain explicitly incomplete.
