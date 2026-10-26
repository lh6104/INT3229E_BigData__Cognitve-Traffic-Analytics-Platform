from cognitive_traffic.storage.postgres import TrafficRepository


def test_nullable_query_parameters_have_explicit_postgres_types(monkeypatch) -> None:
    repository = TrafficRepository("postgresql://unused")
    statements: list[str] = []
    monkeypatch.setattr(repository, "fetch_all", lambda query, parameters=(): statements.append(query) or [])

    repository.roads(None)
    repository.current_traffic(None)
    repository.forecasts(None, None)
    repository.hotspots(None)

    normalized = [" ".join(statement.split()) for statement in statements]
    assert "WHERE (%s::text IS NULL OR city = %s)" in normalized[0]
    assert "(%s::text IS NULL OR current.city = %s)" in normalized[1]
    assert "WHERE (%s::text IS NULL OR forecast.road_id = %s)" in normalized[2]
    assert "AND (%s::integer IS NULL OR forecast.horizon_minutes = %s)" in normalized[2]
    assert "WHERE (%s::text IS NULL OR city = %s)" in normalized[3]
