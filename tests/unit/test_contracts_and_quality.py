import pandas as pd

from ml.training.features import select_feature_columns
from pipelines.quality.run_checks import checks_for_layer, load_contracts
from scripts.build_local_gold_dataset import add_exact_targets


def _base_gold_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "city": ["hanoi", "hanoi", "hanoi", "hanoi"],
            "segment_id": ["HN_001", "HN_001", "HN_001", "HN_001"],
            "time_bucket": pd.date_range("2026-06-12 08:00:00", periods=4, freq="5min"),
            "currentSpeed": [30.0, 31.0, 32.0, 33.0],
            "freeFlowSpeed": [45.0, 45.0, 45.0, 45.0],
            "jamFactor": [2.0, 2.2, 2.4, 2.5],
            "weather_temperature": [31.0, 31.0, 32.0, 32.0],
            "weather_humidity": [70.0, 70.0, 68.0, 68.0],
        }
    )


def test_machine_readable_contracts_define_gold_primary_key():
    contracts = load_contracts()
    assert contracts["gold"]["primary_key"] == ["city", "segment_id", "time_bucket"]
    assert "currentSpeed" in contracts["gold"]["required_columns"]
    assert "gold_cleaned_traffic_features" in contracts["datasets"]


def test_valid_gold_dataframe_passes_critical_contract_checks():
    results = checks_for_layer("gold", _base_gold_frame(), contracts=load_contracts())
    critical_failures = [result for result in results if result.critical and result.status == "FAIL"]
    assert critical_failures == []


def test_missing_required_column_fails():
    df = _base_gold_frame().drop(columns=["currentSpeed"])
    results = checks_for_layer("gold", df, contracts=load_contracts())
    required = next(result for result in results if result.name == "required_columns")
    assert required.status == "FAIL"


def test_duplicate_key_detection_fails_gold_contract():
    df = pd.concat([_base_gold_frame().iloc[[0]], _base_gold_frame().iloc[[0]]], ignore_index=True)
    results = checks_for_layer("gold", df, contracts=load_contracts())
    duplicate = next(result for result in results if result.name == "duplicate_key")
    assert duplicate.status == "FAIL"


def test_invalid_speed_and_jam_factor_fail_range_checks():
    df = _base_gold_frame()
    df.loc[0, "currentSpeed"] = -1
    df.loc[1, "jamFactor"] = 99
    results = checks_for_layer("gold", df, contracts=load_contracts())
    statuses = {result.name: result.status for result in results}
    assert statuses["currentSpeed_range"] == "FAIL"
    assert statuses["jamFactor_range"] == "FAIL"


def test_nullable_rules_fail_non_null_column():
    df = _base_gold_frame()
    df.loc[0, "city"] = None
    results = checks_for_layer("gold", df, contracts=load_contracts())
    nullable = next(result for result in results if result.name == "nullable_contract")
    assert nullable.status == "FAIL"


def test_unallowed_future_or_target_feature_fails_leakage_check():
    df = _base_gold_frame()
    df["actual_future_speed"] = [1.0, 2.0, 3.0, 4.0]
    results = checks_for_layer("gold", df, contracts=load_contracts())
    leakage = next(result for result in results if result.name == "feature_leakage")
    assert leakage.status == "FAIL"


def test_exact_horizon_target_uses_timestamp_join():
    df = _base_gold_frame()
    features = add_exact_targets(df)
    first = features.sort_values("time_bucket").iloc[0]
    assert first["future_speed_15m"] == 33.0
    assert first["has_exact_target_15m"] == 1


def test_leakage_columns_are_excluded_from_training_features():
    df = _base_gold_frame()
    df["target_speed"] = [31.0, 32.0, 33.0, 34.0]
    df["future_speed_15m"] = [32.0, 33.0, 34.0, None]
    df["future_speed_60m"] = [40.0, 41.0, None, None]
    selection = select_feature_columns(df, "target_speed")
    assert "future_speed_15m" not in selection.feature_columns
    assert "future_speed_60m" not in selection.feature_columns
    assert "target_speed" not in selection.feature_columns
