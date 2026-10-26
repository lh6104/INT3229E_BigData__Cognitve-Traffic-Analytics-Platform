from fastapi.testclient import TestClient

from cognitive_traffic.api.main import app, repository


class FakeRepository:
    def ping(self):
        return True

    def roads(self, city):
        return [{"road_id": "HN-001", "city": city or "hanoi", "name": "Test", "category": "primary"}]

    def current_traffic(self, city):
        return []

    def traffic_history(self, road_id, limit):
        return []

    def forecasts(self, road_id, horizon):
        return []

    def hotspots(self, city):
        return []

    def alerts(self, active_only):
        return []

    def current_model(self):
        return {"model_version": "7", "stage": "champion"}

    def model_metrics(self):
        return []

    def data_quality(self):
        return []


app.dependency_overrides[repository] = FakeRepository
client = TestClient(app)


def test_api_is_small_and_operational() -> None:
    paths = set(app.openapi()["paths"])
    assert paths == {
        "/roads",
        "/traffic/current",
        "/traffic/history",
        "/forecasts",
        "/hotspots",
        "/alerts",
        "/models/current",
        "/models/metrics",
        "/system/data-quality",
        "/system/health",
    }
    assert client.get("/system/health").json()["status"] == "healthy"
    assert client.get("/roads?city=hanoi").json()[0]["road_id"] == "HN-001"
