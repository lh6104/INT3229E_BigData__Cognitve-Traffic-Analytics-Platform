from datetime import datetime, timezone

import pytest

from pipelines.transformation.manifest import build_stage_record, manifest_stage, write_manifest


def test_manifest_writer_outputs_json_and_markdown(tmp_path):
    output = tmp_path / "dataset.csv"
    output.write_text("id,value\n1,10\n2,20\n", encoding="utf-8")
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
    stage = build_stage_record(
        run_id="run-1",
        stage_name="silver",
        status="success",
        start_time_utc=start,
        end_time_utc=end,
        input_paths=["data/raw/*.jsonl"],
        output_paths=[output],
    )

    write_manifest(
        {
            "run_id": "run-1",
            "status": "success",
            "start_time_utc": start.isoformat(),
            "end_time_utc": end.isoformat(),
            "duration_seconds": 2.0,
            "stages": [stage],
            "key_outputs": [],
        },
        tmp_path,
    )

    payload = (tmp_path / "pipeline_run_manifest.json").read_text(encoding="utf-8")
    markdown = (tmp_path / "pipeline_run_manifest.md").read_text(encoding="utf-8")
    assert '"stage_name": "silver"' in payload
    assert '"status": "success"' in payload
    assert "| silver | success |" in markdown
    assert "rows=2" in markdown


def test_manifest_stage_writes_failed_status_before_reraising(tmp_path):
    stages = []

    with pytest.raises(RuntimeError):
        with manifest_stage(
            stages,
            run_id="run-failed",
            stage_name="gold",
            input_paths=["silver"],
            output_paths=[tmp_path / "missing"],
            reports_dir=tmp_path,
        ):
            raise RuntimeError("boom")

    payload = (tmp_path / "pipeline_run_manifest.json").read_text(encoding="utf-8")
    assert '"status": "failed"' in payload
    assert '"stage_name": "gold"' in payload
    assert "boom" in payload
