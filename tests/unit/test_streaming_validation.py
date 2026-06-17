from pipelines.streaming.bounded_ingest import inject_invalid_message, validate


def test_valid_traffic_message_passes_validation():
    ok, reason = validate(
        "traffic.raw",
        {
            "city": "hanoi",
            "segment_id": "HN_001",
            "currentSpeed": 30,
            "freeFlowSpeed": 45,
            "jamFactor": 2.5,
        },
    )

    assert ok is True
    assert reason == "ok"


def test_invalid_traffic_range_fails_validation():
    ok, reason = validate(
        "traffic.raw",
        {
            "city": "hanoi",
            "segment_id": "HN_BAD",
            "currentSpeed": -5,
            "freeFlowSpeed": 45,
            "jamFactor": 12,
        },
    )

    assert ok is False
    assert "range" in reason


def test_inject_invalid_adds_dlq_demo_candidate():
    messages = inject_invalid_message([])

    assert len(messages) == 1
    topic, payload = messages[0]
    assert topic == "traffic.raw"
    assert payload["injected_invalid"] is True
