from pathlib import Path

import yaml

from cognitive_traffic.monitoring.registry_report import build_report, main

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "configs/sources.yaml"
DATASETS = ROOT / "configs/datasets.yaml"


def test_report_is_deterministic_and_labels_unverified_evidence() -> None:
    report = build_report(SOURCES, DATASETS)

    assert report == build_report(SOURCES, DATASETS)
    assert len(report["sources_sha256"]) == 64
    assert len(report["datasets_sha256"]) == 64
    assert report["configured_points"] == 12
    assert report["points_by_city"] == {"hanoi": 6, "hcmc": 6}
    assert all(point["mapping_status"] == "unverified" for point in report["points"])
    assert report["datasets"][0]["dataset_id"] == "largest"
    benchmark_eligibility = [
        dataset["eligible_for_live_current"]
        for dataset in report["datasets"]
        if dataset["dataset_id"] != "vn-mvp-12"
    ]
    assert not any(benchmark_eligibility)
    assert next(dataset for dataset in report["datasets"] if dataset["dataset_id"] == "vn-mvp-12")[
        "eligible_for_live_current"
    ]
    assert "reporting_points" not in report


def test_missing_config_returns_exit_two_without_json(capsys) -> None:
    assert main(["--sources", "missing-registry.yaml", "--datasets", str(DATASETS)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err


def test_report_reflects_input_byte_changes(tmp_path: Path) -> None:
    sources_data = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    sources = tmp_path / "sources.yaml"
    datasets = tmp_path / "datasets.yaml"
    sources.write_text(yaml.safe_dump(sources_data), encoding="utf-8")
    datasets.write_bytes(DATASETS.read_bytes())

    first = build_report(sources, datasets)
    sources.write_text(sources.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    second = build_report(sources, datasets)

    assert first["sources_sha256"] != second["sources_sha256"]
    assert first["points"] == second["points"]
