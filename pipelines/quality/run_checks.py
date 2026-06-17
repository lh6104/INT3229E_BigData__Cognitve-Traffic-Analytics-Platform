"""Data quality gate for local Bronze/Silver/Gold datasets."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT_PATH = PROJECT_ROOT / "docs" / "data_contracts" / "contracts.yaml"
LEGACY_CONTRACT_PATH = PROJECT_ROOT / "docs" / "data_contracts" / "contracts.json"


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str
    critical: bool = True


def table_path(path: Path) -> Path:
    if path.is_file():
        return path
    if path.with_suffix(".parquet").exists():
        return path.with_suffix(".parquet")
    if path.with_suffix(".csv").exists():
        return path.with_suffix(".csv")
    if path.with_suffix(".jsonl").exists():
        return path.with_suffix(".jsonl")
    raise FileNotFoundError(f"Dataset not found: {path}")


def read_dataset(path: Path) -> pd.DataFrame:
    resolved = table_path(path)
    if resolved.suffix == ".parquet":
        return pd.read_parquet(resolved)
    if resolved.suffix == ".jsonl":
        return pd.read_json(resolved, lines=True)
    return pd.read_csv(resolved)


def load_contracts(path: Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:
    if not path.exists() and LEGACY_CONTRACT_PATH.exists():
        path = LEGACY_CONTRACT_PATH
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(text) or {}
        datasets = payload.get("datasets", {})
        for layer in ("bronze", "silver", "gold"):
            payload.setdefault(layer, next((contract for contract in datasets.values() if contract.get("layer") == layer), {}))
        return payload
    return json.loads(text)


def _contract_candidates(contracts: dict[str, Any]) -> dict[str, Any]:
    datasets = contracts.get("datasets")
    if isinstance(datasets, dict):
        return datasets
    return contracts


def _legacy_contract(layer: str, contract: dict[str, Any]) -> dict[str, Any]:
    if "required_columns" in contract and isinstance(contract.get("required_columns"), list):
        required = {column: {"type": contract.get("types", {}).get(column, "string"), "nullable": contract.get("nullable", {}).get(column, True)} for column in contract.get("required_columns", [])}
        for column, bounds in contract.get("ranges", {}).items():
            required.setdefault(column, {"type": contract.get("types", {}).get(column, "numeric"), "nullable": True})
            if isinstance(bounds, list) and len(bounds) == 2:
                required[column]["min"] = bounds[0]
                required[column]["max"] = bounds[1]
        return {**contract, "dataset_name": layer, "required_columns": required}
    return {**contract, "dataset_name": contract.get("dataset_name", layer)}


def contract_for_layer(layer: str, contracts: dict[str, Any] | None = None) -> dict[str, Any]:
    contracts = contracts if contracts is not None else load_contracts()
    layer = layer.lower()
    candidates = _contract_candidates(contracts)
    if layer in candidates:
        return _legacy_contract(layer, candidates[layer])
    for name, contract in candidates.items():
        if contract.get("layer") == layer:
            return _legacy_contract(str(name), contract)
    return {}


def contract_for_dataset(dataset: str | None, layer: str, contracts: dict[str, Any] | None = None) -> dict[str, Any]:
    contracts = contracts if contracts is not None else load_contracts()
    candidates = _contract_candidates(contracts)
    if dataset and dataset in candidates:
        return _legacy_contract(dataset, candidates[dataset])
    return contract_for_layer(layer, contracts)


def required_column_names(contract: dict[str, Any]) -> list[str]:
    required = contract.get("required_columns", {})
    if isinstance(required, dict):
        return list(required)
    return list(required or [])


def nullable_rules(contract: dict[str, Any]) -> dict[str, bool]:
    if isinstance(contract.get("nullable"), dict):
        return dict(contract["nullable"])
    rules: dict[str, bool] = {}
    for group_name in ("required_columns", "optional_columns"):
        columns = contract.get(group_name, {})
        if isinstance(columns, dict):
            for column, spec in columns.items():
                rules[column] = bool(spec.get("nullable", group_name == "optional_columns"))
    return rules


def type_rules(contract: dict[str, Any]) -> dict[str, str]:
    if isinstance(contract.get("types"), dict):
        return dict(contract["types"])
    rules: dict[str, str] = {}
    for group_name in ("required_columns", "optional_columns"):
        columns = contract.get(group_name, {})
        if isinstance(columns, dict):
            for column, spec in columns.items():
                if "type" in spec:
                    rules[column] = str(spec["type"])
    return rules


def range_rules(contract: dict[str, Any]) -> dict[str, list[float | None]]:
    if isinstance(contract.get("ranges"), dict):
        return dict(contract["ranges"])
    rules: dict[str, list[float | None]] = {}
    for group_name in ("required_columns", "optional_columns"):
        columns = contract.get(group_name, {})
        if isinstance(columns, dict):
            for column, spec in columns.items():
                if "min" in spec or "max" in spec:
                    rules[column] = [spec.get("min"), spec.get("max")]
    return rules


def check_required_columns(df: pd.DataFrame, columns: list[str]) -> CheckResult:
    missing = [column for column in columns if column not in df.columns]
    return CheckResult("required_columns", "FAIL" if missing else "PASS", f"missing={missing}")


def check_null_ratio(df: pd.DataFrame, columns: list[str], threshold: float) -> CheckResult:
    ratios: dict[str, float] = {}
    for column in columns:
        if column in df.columns:
            ratios[column] = float(df[column].isna().mean())
    failed = {key: value for key, value in ratios.items() if value > threshold}
    return CheckResult("null_ratio", "FAIL" if failed else "PASS", f"threshold={threshold} ratios={failed or ratios}")


def check_nullable_contract(df: pd.DataFrame, nullable: dict[str, bool]) -> CheckResult:
    required_non_null = [column for column, is_nullable in nullable.items() if not is_nullable and column in df.columns]
    failed = {column: int(df[column].isna().sum()) for column in required_non_null if int(df[column].isna().sum()) > 0}
    return CheckResult("nullable_contract", "FAIL" if failed else "PASS", f"non_null_violations={failed}")


def check_duplicate_key(df: pd.DataFrame, key: list[str]) -> CheckResult:
    usable = [column for column in key if column in df.columns]
    if not usable:
        return CheckResult("duplicate_key", "FAIL", f"key columns missing: {key}")
    duplicates = int(df.duplicated(subset=usable).sum())
    return CheckResult("duplicate_key", "FAIL" if duplicates else "PASS", f"key={usable} duplicates={duplicates}")


def check_range(df: pd.DataFrame, column: str, lower: float, upper: float) -> CheckResult:
    if column not in df.columns:
        return CheckResult(f"{column}_range", "SKIP", "column not present", critical=False)
    values = pd.to_numeric(df[column], errors="coerce")
    bad = int((~values.between(lower, upper) & values.notna()).sum())
    return CheckResult(f"{column}_range", "FAIL" if bad else "PASS", f"range=[{lower},{upper}] bad_rows={bad}")


def check_minmax_range(df: pd.DataFrame, column: str, lower: float | None, upper: float | None) -> CheckResult:
    if column not in df.columns:
        return CheckResult(f"{column}_range", "SKIP", "column not present", critical=False)
    values = pd.to_numeric(df[column], errors="coerce")
    mask = values.notna()
    if lower is not None:
        mask &= values >= float(lower)
    if upper is not None:
        mask &= values <= float(upper)
    bad = int((~mask & values.notna()).sum())
    return CheckResult(f"{column}_range", "FAIL" if bad else "PASS", f"min={lower} max={upper} bad_rows={bad}")


def check_type(df: pd.DataFrame, column: str, expected_type: str) -> CheckResult:
    if column not in df.columns:
        return CheckResult(f"{column}_type", "SKIP", "column not present", critical=False)
    series = df[column]
    expected_type = expected_type.lower()
    if expected_type == "numeric":
        invalid = int(pd.to_numeric(series.dropna(), errors="coerce").isna().sum())
    elif expected_type == "timestamp":
        invalid = int(pd.to_datetime(series.dropna(), errors="coerce").isna().sum())
    elif expected_type == "string":
        invalid = int(series.dropna().map(lambda value: not isinstance(value, str)).sum())
    elif expected_type == "object":
        invalid = 0
    else:
        return CheckResult(f"{column}_type", "SKIP", f"unknown expected_type={expected_type}", critical=False)
    return CheckResult(f"{column}_type", "FAIL" if invalid else "PASS", f"expected={expected_type} invalid_rows={invalid}")


def check_timestamp_order(df: pd.DataFrame) -> CheckResult:
    column = "time_bucket" if "time_bucket" in df.columns else "timestamp" if "timestamp" in df.columns else None
    if column is None:
        return CheckResult("timestamp_order", "FAIL", "no timestamp/time_bucket column")
    work = df.copy()
    work[column] = pd.to_datetime(work[column], errors="coerce")
    bad_nulls = int(work[column].isna().sum())
    group_cols = [column for column in ["city", "segment_id"] if column in work.columns]
    inversions = 0
    if group_cols:
        for _, group in work.sort_values(group_cols + [column]).groupby(group_cols):
            inversions += int((group[column].diff().dropna() < pd.Timedelta(0)).sum())
    return CheckResult("timestamp_order", "FAIL" if bad_nulls or inversions else "PASS", f"nulls={bad_nulls} inversions={inversions}")


def check_feature_leakage(df: pd.DataFrame, allowed: list[str] | None = None) -> CheckResult:
    allowed_set = set(allowed or [])
    blocked_tokens = ["future_", "target", "prediction", "label", "actual_future"]
    found = [
        column
        for column in df.columns
        if column not in allowed_set and any(token in column.lower() for token in blocked_tokens)
    ]
    return CheckResult("feature_leakage", "FAIL" if found else "PASS", f"suspicious_columns={found}")


def check_freshness(df: pd.DataFrame, timestamp_column: str | None, warning_hours: float | None) -> CheckResult:
    if not timestamp_column or timestamp_column not in df.columns:
        return CheckResult("freshness", "SKIP", "timestamp column not configured or not present", critical=False)
    timestamps = pd.to_datetime(df[timestamp_column], utc=True, errors="coerce").dropna()
    if timestamps.empty:
        return CheckResult("freshness", "WARN", f"{timestamp_column} has no parseable timestamps", critical=False)
    max_ts = timestamps.max()
    age_hours = max(0.0, (datetime.now(timezone.utc) - max_ts.to_pydatetime()).total_seconds() / 3600.0)
    status = "WARN" if warning_hours is not None and age_hours > warning_hours else "PASS"
    return CheckResult(
        "freshness",
        status,
        f"timestamp_column={timestamp_column} max_timestamp={max_ts.isoformat()} age_hours={age_hours:.2f} warning_hours={warning_hours}",
        critical=False,
    )


def check_missing_feature_coverage(df: pd.DataFrame, columns: list[str], name: str, warn_threshold: float = 0.20) -> CheckResult:
    present = [column for column in columns if column in df.columns]
    if not present:
        return CheckResult(name, "SKIP", "coverage columns not present", critical=False)
    ratios = {column: float(df[column].isna().mean()) for column in present}
    worst = max(ratios.values()) if ratios else 0.0
    status = "WARN" if worst > warn_threshold else "PASS"
    return CheckResult(name, status, f"missing_ratios={ratios} warn_threshold={warn_threshold}", critical=False)


def check_segment_time_bucket_coverage(df: pd.DataFrame) -> CheckResult:
    if "segment_id" not in df.columns or "time_bucket" not in df.columns:
        return CheckResult("segment_time_bucket_coverage", "SKIP", "segment_id/time_bucket not present", critical=False)
    work = df[["segment_id", "time_bucket"]].copy()
    work["time_bucket"] = pd.to_datetime(work["time_bucket"], errors="coerce")
    work = work.dropna()
    if work.empty:
        return CheckResult("segment_time_bucket_coverage", "WARN", "no parseable segment/time_bucket rows", critical=False)
    bucket_counts = work.groupby("segment_id")["time_bucket"].nunique().sort_values()
    median = float(bucket_counts.median())
    low_segments = bucket_counts[bucket_counts < max(1, median * 0.25)].head(10)
    status = "WARN" if len(low_segments) else "PASS"
    detail = {
        "segments": int(bucket_counts.shape[0]),
        "median_buckets": median,
        "lowest_segments": low_segments.to_dict(),
    }
    return CheckResult("segment_time_bucket_coverage", status, f"{detail}", critical=False)


def check_referential_coverage(df: pd.DataFrame, name: str, spec: dict[str, Any]) -> CheckResult:
    key = spec.get("key", [])
    usable = [column for column in key if column in df.columns]
    if len(usable) != len(key):
        if spec.get("skip_if_missing_columns"):
            return CheckResult(f"{name}_coverage", "SKIP", f"missing source key columns={sorted(set(key) - set(usable))}", critical=False)
        return CheckResult(f"{name}_coverage", "WARN", f"missing source key columns={sorted(set(key) - set(usable))}", critical=False)

    ref_path = PROJECT_ROOT / str(spec.get("path", ""))
    try:
        ref_df = read_dataset(ref_path)
    except Exception as exc:
        return CheckResult(f"{name}_coverage", "WARN", f"reference unavailable: {exc}", critical=False)

    ref_usable = [column for column in key if column in ref_df.columns]
    if len(ref_usable) != len(key):
        if spec.get("skip_if_missing_columns"):
            return CheckResult(f"{name}_coverage", "SKIP", f"missing reference key columns={sorted(set(key) - set(ref_usable))}", critical=False)
        return CheckResult(f"{name}_coverage", "WARN", f"missing reference key columns={sorted(set(key) - set(ref_usable))}", critical=False)

    left = df[usable].dropna().drop_duplicates().copy()
    right = ref_df[key].dropna().drop_duplicates().copy()
    for column in key:
        if "time" in column:
            left[column] = pd.to_datetime(left[column], errors="coerce").astype(str)
            right[column] = pd.to_datetime(right[column], errors="coerce").astype(str)
        else:
            left[column] = left[column].astype(str)
            right[column] = right[column].astype(str)
    if left.empty:
        return CheckResult(f"{name}_coverage", "SKIP", "no non-null source keys", critical=False)
    matched = left.merge(right.assign(_matched=1), on=key, how="left")["_matched"].fillna(0)
    ratio = float((matched == 1).mean())
    threshold = float(spec.get("warning_threshold", 0.95))
    status = "WARN" if ratio < threshold else "PASS"
    return CheckResult(
        f"{name}_coverage",
        status,
        f"coverage_ratio={ratio:.4f} threshold={threshold} source_keys={len(left)} reference_keys={len(right)}",
        critical=False,
    )


def checks_for_layer(layer: str, df: pd.DataFrame, contracts: dict[str, Any] | None = None, dataset: str | None = None) -> list[CheckResult]:
    layer = layer.lower()
    contract = contract_for_dataset(dataset, layer, contracts)
    required = required_column_names(contract)
    key = contract.get("primary_key")
    if not required:
        required = ["topic", "ingested_at_utc", "payload"] if layer == "bronze" else ["city", "segment_id", "time_bucket", "currentSpeed", "freeFlowSpeed", "jamFactor"]
    if not key:
        key = ["topic", "idempotency_key"] if layer == "bronze" else ["city", "segment_id", "time_bucket"]
    nullable = nullable_rules(contract)
    non_nullable_required = [column for column in required if column in df.columns and nullable.get(column, True) is False]

    checks = [
        check_required_columns(df, required),
        check_null_ratio(df, non_nullable_required, threshold=0.05),
        check_nullable_contract(df, nullable),
        check_duplicate_key(df, key),
        check_timestamp_order(df),
        check_feature_leakage(df, contract.get("leakage_allowed_columns", [])),
        check_freshness(df, contract.get("timestamp_column"), contract.get("freshness_warning_hours")),
    ]
    for column, expected_type in type_rules(contract).items():
        checks.append(check_type(df, column, expected_type))
    ranges = range_rules(contract) or {
        "currentSpeed": [0, 150],
        "freeFlowSpeed": [1, 180],
        "jamFactor": [0, 10],
        "temp": [-50, 60],
        "humidity": [0, 100],
    }
    for column, bounds in ranges.items():
        if isinstance(bounds, list) and len(bounds) == 2:
            checks.append(check_minmax_range(df, column, bounds[0], bounds[1]))
    for name, spec in contract.get("referential_checks", {}).items():
        checks.append(check_referential_coverage(df, name, spec))
    if layer == "gold":
        checks.append(check_missing_feature_coverage(df, ["weather_temperature", "weather_humidity", "weather_rain_1h"], "weather_feature_coverage"))
        checks.append(
            check_missing_feature_coverage(
                df,
                ["has_any_event", "news_event_count_1h", "max_event_severity_1h"],
                "event_feature_coverage",
            )
        )
        checks.append(check_segment_time_bucket_coverage(df))
    return checks


def write_report(results: list[CheckResult], output: Path, metadata: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Data Quality Report",
        "",
        f"Generated at: {metadata['generated_at']}",
        f"Layer: `{metadata['layer']}`",
        f"Input: `{metadata['input']}`",
        f"Rows: `{metadata['rows']}`",
        "",
        "| Check | Status | Critical | Detail |",
        "|---|---|---:|---|",
    ]
    for result in results:
        detail = str(result.detail).replace("|", "\\|")
        lines.append(f"| {result.name} | {result.status} | {result.critical} | {detail} |")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_output = output.with_suffix(".json")
    json_output.write_text(
        json.dumps(
            {
                "metadata": metadata,
                "results": [result.__dict__ for result in results],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layer", default="gold", choices=["bronze", "silver", "gold"])
    parser.add_argument("--input", default="data/gold/cleaned_traffic_features")
    parser.add_argument("--output", default="reports/data_quality_report.md")
    parser.add_argument("--dataset", default=None, help="Dataset key from docs/data_contracts/contracts.yaml")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = PROJECT_ROOT / input_path
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    df = read_dataset(input_path)
    results = checks_for_layer(args.layer, df, dataset=args.dataset)
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "layer": args.layer,
        "dataset": args.dataset,
        "input": str(input_path.relative_to(PROJECT_ROOT) if input_path.is_relative_to(PROJECT_ROOT) else input_path),
        "rows": int(len(df)),
        "contract": str(DEFAULT_CONTRACT_PATH.relative_to(PROJECT_ROOT)) if DEFAULT_CONTRACT_PATH.exists() else None,
    }
    write_report(results, output_path, metadata)
    failed = [result for result in results if result.critical and result.status == "FAIL"]
    for result in results:
        print(f"{result.status:4} {result.name}: {result.detail}")
    print(f"Wrote {output_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
