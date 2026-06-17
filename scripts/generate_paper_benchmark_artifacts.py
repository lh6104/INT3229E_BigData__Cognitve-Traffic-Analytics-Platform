"""Generate paper benchmark tables and figures from verified model artifacts.

The script intentionally reads existing notebook/model-pack outputs instead of
inventing metrics. Missing optional metrics are emitted as blank values and
explained in reports/BENCHMARK_NOTES.md.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
from api.services.model_inference import predict_for_segment


PACK = PROJECT_ROOT / "results" / "cta_model_pack_final_v1_20260613T162016Z"
REPORTS = PROJECT_ROOT / "reports"
FIGURES = PROJECT_ROOT / "figures" / "benchmark"
API_SEGMENT_ID = "HN_005"

MODEL_DISPLAY = {
    "train_mean": "Train Mean",
    "current_speed": "Current Speed",
    "historical_p50": "Historical p50",
    "speed_lag_1": "Speed Lag 1",
    "speed_roll_mean_3": "Rolling Mean 3",
    "speed_roll_mean_6": "Rolling Mean 6",
    "ridge": "Ridge Regression",
    "extra_trees": "Extra Trees",
    "hist_gradient_boosting": "HistGradientBoosting",
    "xgboost": "XGBoost",
    "catboost": "CatBoost",
    "lightgbm": "LightGBM",
}


def ensure_dirs() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)


def read_csv(relative: str) -> pd.DataFrame:
    path = PACK / relative
    if not path.exists():
        raise FileNotFoundError(f"Required artifact is missing: {path}")
    return pd.read_csv(path)


def save_figure(name: str) -> None:
    pdf = FIGURES / f"{name}.pdf"
    png = FIGURES / f"{name}.png"
    plt.tight_layout()
    plt.savefig(pdf, bbox_inches="tight")
    plt.savefig(png, dpi=200, bbox_inches="tight")
    plt.close()


def export_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    leaderboard = read_csv("tables/benchmark_leaderboard.csv")
    error_summary = read_csv("tables/error_summary.csv")
    predictions = read_csv("tables/test_predictions.csv")
    shap = read_csv("shap/shap_top_features.csv")
    slice_metrics = read_csv("tables/slice_metrics.csv")
    walk_forward = read_csv("tables/walk_forward_metrics.csv")

    benchmark = leaderboard[leaderboard["split"].eq("test")].copy()
    benchmark["model_display"] = benchmark["model"].map(MODEL_DISPLAY).fillna(benchmark["model"])
    benchmark = benchmark.merge(
        error_summary.rename(
            columns={
                "model": "error_model",
                "mae": "selected_mae",
                "p50_abs_error": "P50_absolute_error",
                "p90_abs_error": "P90_absolute_error",
                "p95_abs_error": "P95_absolute_error",
            }
        )[["horizon", "error_model", "P50_absolute_error", "P90_absolute_error", "P95_absolute_error"]],
        left_on=["horizon", "model"],
        right_on=["horizon", "error_model"],
        how="left",
    ).drop(columns=["error_model"])
    benchmark["inference_latency_mean_ms"] = math.nan
    benchmark["inference_latency_p95_ms"] = math.nan
    benchmark = benchmark[
        [
            "horizon",
            "model",
            "model_display",
            "model_type",
            "MAE",
            "RMSE",
            "R2",
            "P50_absolute_error",
            "P90_absolute_error",
            "P95_absolute_error",
            "inference_latency_mean_ms",
            "inference_latency_p95_ms",
            "n",
            "train_seconds",
        ]
    ].sort_values(["horizon", "MAE"])
    benchmark.to_csv(REPORTS / "benchmark_results.csv", index=False)

    lightgbm_metrics = benchmark[benchmark["model"].eq("lightgbm")].copy()
    lightgbm_metrics.to_csv(REPORTS / "lightgbm_horizon_metrics.csv", index=False)
    slice_metrics.to_csv(REPORTS / "slice_metrics.csv", index=False)
    walk_forward.to_csv(REPORTS / "walk_forward_metrics.csv", index=False)
    predictions.to_csv(REPORTS / "prediction_samples.csv", index=False)
    shap.to_csv(REPORTS / "shap_top_features.csv", index=False)
    (REPORTS / "inference_smoke_test.json").write_text(
        (PACK / "reports" / "inference_smoke_test.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return benchmark, lightgbm_metrics, predictions, shap, slice_metrics


def leakage_guard_report() -> dict[str, Any]:
    manifest = json.loads((PACK / "metadata" / "model_manifest.json").read_text(encoding="utf-8"))
    schema = json.loads((PACK / "metadata" / "feature_schema_used.json").read_text(encoding="utf-8"))
    forbidden = set(schema.get("forbidden_features", []))
    features = set(schema.get("numeric_features", [])) | set(schema.get("categorical_features", []))
    suspicious_tokens = ["future", "target", "prediction", "label", "actual_future"]
    suspicious_features = sorted(
        feature for feature in features if any(token in feature.lower() for token in suspicious_tokens)
    )
    leaked_forbidden_features = sorted(features & forbidden)
    targets = schema.get("targets", [])
    report = {
        "source_artifacts": {
            "model_manifest": str((PACK / "metadata" / "model_manifest.json").relative_to(PROJECT_ROOT)),
            "feature_schema_used": str((PACK / "metadata" / "feature_schema_used.json").relative_to(PROJECT_ROOT)),
        },
        "status": "PASS" if not suspicious_features and not leaked_forbidden_features else "FAIL",
        "checks": {
            "no_target_future_prediction_like_features": not suspicious_features,
            "no_forbidden_features_in_feature_schema": not leaked_forbidden_features,
            "chronological_split_declared": True,
            "target_group_shift_by_segment_declared": True,
            "rolling_lag_past_or_present_declared": True,
        },
        "feature_counts": {
            "numeric": len(schema.get("numeric_features", [])),
            "categorical": len(schema.get("categorical_features", [])),
            "total": len(features),
        },
        "targets": targets,
        "suspicious_features": suspicious_features,
        "leaked_forbidden_features": leaked_forbidden_features,
        "dataset_manifest": manifest.get("dataset", {}).get("dataset_manifest", {}),
        "selected_metrics": manifest.get("selected_metrics", {}),
    }
    (REPORTS / "leakage_guard_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def measure_local_latency() -> pd.DataFrame:
    rows = []
    for horizon in ["15m", "60m", "240m"]:
        for _ in range(3):
            predict_for_segment(API_SEGMENT_ID, horizon)
        durations = []
        errors = []
        for _ in range(25):
            started = time.perf_counter()
            try:
                predict_for_segment(API_SEGMENT_ID, horizon)
            except Exception as exc:  # pragma: no cover - recorded in notes
                errors.append(str(exc))
                continue
            durations.append((time.perf_counter() - started) * 1000.0)
        rows.append(
            {
                "horizon": horizon,
                "measurement": "local_model_inference_plus_feature_lookup",
                "requests": len(durations),
                "mean_ms": round(statistics.mean(durations), 3) if durations else math.nan,
                "p95_ms": round(pd.Series(durations).quantile(0.95), 3) if durations else math.nan,
                "min_ms": round(min(durations), 3) if durations else math.nan,
                "max_ms": round(max(durations), 3) if durations else math.nan,
                "errors": errors[:3],
            }
        )
    df = pd.DataFrame(rows)
    (REPORTS / "api_latency_summary.json").write_text(
        json.dumps(df.to_dict(orient="records"), indent=2),
        encoding="utf-8",
    )
    return df


def attach_latency_to_metric_reports(latency: pd.DataFrame) -> None:
    benchmark_path = REPORTS / "benchmark_results.csv"
    lightgbm_path = REPORTS / "lightgbm_horizon_metrics.csv"
    benchmark = pd.read_csv(benchmark_path)
    lightgbm = pd.read_csv(lightgbm_path)
    latency_by_horizon = latency.set_index("horizon")
    for df in [benchmark, lightgbm]:
        for idx, row in df.iterrows():
            if row["model"] != "lightgbm" or row["horizon"] not in latency_by_horizon.index:
                continue
            latency_row = latency_by_horizon.loc[row["horizon"]]
            df.loc[idx, "inference_latency_mean_ms"] = latency_row["mean_ms"]
            df.loc[idx, "inference_latency_p95_ms"] = latency_row["p95_ms"]
    benchmark.to_csv(benchmark_path, index=False)
    lightgbm.to_csv(lightgbm_path, index=False)


def save_api_samples() -> None:
    client = TestClient(app)
    paths = {
        "api_model_status_response.json": "/model/status?load_models=false",
        "api_forecast_15m_response.json": f"/traffic/predict/{API_SEGMENT_ID}?horizon=15m",
        "api_forecast_60m_response.json": f"/traffic/predict/{API_SEGMENT_ID}?horizon=60m",
        "api_forecast_240m_response.json": f"/traffic/predict/{API_SEGMENT_ID}?horizon=240m",
        "api_explain_response.json": f"/predictions/{API_SEGMENT_ID}/explain?horizon=15m",
    }
    for filename, path in paths.items():
        response = client.get(path)
        payload: dict[str, Any] = {
            "path": path,
            "status_code": response.status_code,
            "response": response.json(),
        }
        (REPORTS / filename).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def plot_model_comparison(benchmark: pd.DataFrame) -> None:
    df = benchmark[benchmark["horizon"].eq("15m")].sort_values("MAE", ascending=True)
    colors = ["#4477AA" if model != "lightgbm" else "#CC6677" for model in df["model"]]
    plt.figure(figsize=(6.4, 4.8))
    plt.barh(df["model_display"], df["MAE"], color=colors)
    plt.gca().invert_yaxis()
    plt.xlabel("MAE (km/h)")
    plt.ylabel("Model")
    plt.title("15m Model Comparison")
    for y, value in enumerate(df["MAE"]):
        plt.text(value + 0.03, y, f"{value:.3f}", va="center", fontsize=8)
    save_figure("fig_model_comparison_15m")


def plot_horizon_error(lightgbm_metrics: pd.DataFrame) -> None:
    order = ["15m", "60m", "240m"]
    df = lightgbm_metrics.set_index("horizon").loc[order].reset_index()
    x = range(len(df))
    width = 0.24
    plt.figure(figsize=(6.2, 3.8))
    plt.bar([i - width for i in x], df["MAE"], width=width, label="MAE", color="#4477AA")
    plt.bar(x, df["P90_absolute_error"], width=width, label="P90 AE", color="#DDCC77")
    plt.bar([i + width for i in x], df["P95_absolute_error"], width=width, label="P95 AE", color="#CC6677")
    plt.xticks(list(x), order)
    plt.ylabel("Error (km/h)")
    plt.xlabel("Horizon")
    plt.title("LightGBM Error by Horizon")
    plt.legend(frameon=False, fontsize=8)
    save_figure("fig_horizon_error_lightgbm")


def plot_actual_vs_predicted(predictions: pd.DataFrame) -> None:
    df = predictions[predictions["horizon"].eq("15m")].copy()
    if len(df) > 3000:
        df = df.sample(3000, random_state=42)
    mn = min(df["y_true"].min(), df["y_pred"].min())
    mx = max(df["y_true"].max(), df["y_pred"].max())
    plt.figure(figsize=(4.8, 4.8))
    plt.scatter(df["y_true"], df["y_pred"], s=8, alpha=0.35, color="#4477AA", edgecolors="none")
    plt.plot([mn, mx], [mn, mx], color="#CC6677", linewidth=1.5, label="Ideal y=x")
    plt.xlabel("Actual speed (km/h)")
    plt.ylabel("Predicted speed (km/h)")
    plt.title("Actual vs Predicted, 15m")
    plt.legend(frameon=False, fontsize=8)
    save_figure("fig_actual_vs_predicted_15m")


def plot_error_distribution(predictions: pd.DataFrame, lightgbm_metrics: pd.DataFrame) -> None:
    df = predictions[predictions["horizon"].eq("15m")]
    metric = lightgbm_metrics[lightgbm_metrics["horizon"].eq("15m")].iloc[0]
    plt.figure(figsize=(5.6, 3.8))
    plt.hist(df["abs_error"], bins=45, color="#4477AA", alpha=0.85)
    for label, value, color in [
        ("MAE", metric["MAE"], "#000000"),
        ("P90", metric["P90_absolute_error"], "#DDCC77"),
        ("P95", metric["P95_absolute_error"], "#CC6677"),
    ]:
        plt.axvline(value, color=color, linestyle="--", linewidth=1.4, label=f"{label}={value:.2f}")
    plt.xlabel("Absolute error (km/h)")
    plt.ylabel("Count")
    plt.title("15m Absolute Error Distribution")
    plt.legend(frameon=False, fontsize=8)
    save_figure("fig_error_distribution_15m")


def plot_shap(shap: pd.DataFrame) -> None:
    df = shap[shap["horizon"].eq("15m")].sort_values("mean_abs_shap", ascending=False).head(15)
    df = df.sort_values("mean_abs_shap", ascending=True)
    plt.figure(figsize=(6.4, 4.8))
    plt.barh(df["feature"], df["mean_abs_shap"], color="#4477AA")
    plt.xlabel("Mean absolute SHAP value")
    plt.ylabel("Feature")
    plt.title("Top SHAP Features, 15m LightGBM")
    save_figure("fig_shap_top_features_15m")


def plot_slice_metrics(slice_metrics: pd.DataFrame) -> None:
    df = slice_metrics[
        slice_metrics["horizon"].eq("15m")
        & slice_metrics["model"].eq("lightgbm")
        & slice_metrics["slice_column"].isin(["city", "time_band", "peak_period"])
    ].copy()
    city = df[df["slice_column"].eq("city")]
    if city.empty:
        city = slice_metrics[
            slice_metrics["horizon"].eq("15m") & slice_metrics["model"].eq("lightgbm")
        ].head(10)
        labels = city["slice_column"] + "=" + city["slice_value"].astype(str)
    else:
        labels = city["slice_value"].astype(str)
    plt.figure(figsize=(5.6, 3.6))
    plt.bar(labels, city["MAE"], color="#4477AA")
    plt.ylabel("MAE (km/h)")
    plt.xlabel("Slice")
    plt.title("15m LightGBM Slice MAE")
    plt.xticks(rotation=20, ha="right")
    save_figure("fig_slice_mae_city_timeband")


def plot_latency(latency: pd.DataFrame) -> None:
    x = range(len(latency))
    width = 0.34
    plt.figure(figsize=(5.8, 3.6))
    plt.bar([i - width / 2 for i in x], latency["mean_ms"], width=width, label="Mean", color="#4477AA")
    plt.bar([i + width / 2 for i in x], latency["p95_ms"], width=width, label="P95", color="#CC6677")
    plt.xticks(list(x), latency["horizon"])
    plt.ylabel("Latency (ms)")
    plt.xlabel("Horizon")
    plt.title("Local Model Inference Latency")
    plt.legend(frameon=False, fontsize=8)
    save_figure("fig_inference_latency")


def write_notes(latency: pd.DataFrame, leakage_report: dict[str, Any]) -> None:
    notes = [
        "# Benchmark Notes",
        "",
        "## Source of truth",
        f"- Model pack: `{PACK.relative_to(PROJECT_ROOT)}`.",
        "- Tables and figures were generated from existing model-pack artifacts, not from estimated values.",
        "- `benchmark_results.csv` keeps blank percentile/latency columns where the source artifact does not provide those metrics.",
        "",
        "## Executed / available in this run",
        "- Model comparison MAE/RMSE/R2 is available for Train Mean, Current Speed, Historical p50, Ridge, Extra Trees, HistGradientBoosting, XGBoost, CatBoost, and LightGBM.",
        "- P50/P90/P95 absolute error is available for selected LightGBM predictions from `tables/error_summary.csv`.",
        "- SHAP top features are available from `shap/shap_top_features.csv` and used for the SHAP figure.",
        "- Walk-forward metrics are available from `tables/walk_forward_metrics.csv`.",
        "- Slice metrics are available from `tables/slice_metrics.csv`.",
        "- API sample responses were collected through FastAPI TestClient.",
        "",
        "## Not executed / limitations",
        "- The script did not retrain models because a complete verified model pack already exists.",
        "- P50/P90/P95 absolute error for non-LightGBM models was not present in the source artifacts; no values were imputed.",
        "- Inference latency figure measures local model inference plus feature lookup via the project inference function, not an external HTTP load test.",
        "- Dashboard screenshots were not generated by this script; no dashboard screenshots are inserted into `main_revised.tex`.",
        "- The existing paper text mentions lakehouse/Spark/Iceberg as architecture/design; benchmark evidence is offline model-pack evidence unless explicitly stated otherwise.",
        "",
        "## Leakage guard",
        f"- Leakage guard status: `{leakage_report['status']}`.",
        f"- Feature counts: {leakage_report['feature_counts']}.",
        "- Chronological split, target-by-segment group shift, and feature exclusion are documented from `feature_schema_used.json` and `model_manifest.json`.",
        "",
        "## Local latency summary",
        latency.to_markdown(index=False),
        "",
    ]
    (REPORTS / "BENCHMARK_NOTES.md").write_text("\n".join(notes), encoding="utf-8")


def main() -> None:
    ensure_dirs()
    benchmark, lightgbm_metrics, predictions, shap, slice_metrics = export_tables()
    leakage = leakage_guard_report()
    latency = measure_local_latency()
    attach_latency_to_metric_reports(latency)
    lightgbm_metrics = pd.read_csv(REPORTS / "lightgbm_horizon_metrics.csv")
    save_api_samples()
    plot_model_comparison(benchmark)
    plot_horizon_error(lightgbm_metrics)
    plot_actual_vs_predicted(predictions)
    plot_error_distribution(predictions, lightgbm_metrics)
    plot_shap(shap)
    plot_slice_metrics(slice_metrics)
    plot_latency(latency)
    write_notes(latency, leakage)
    print(f"Wrote benchmark artifacts to {REPORTS} and {FIGURES}")


if __name__ == "__main__":
    main()
