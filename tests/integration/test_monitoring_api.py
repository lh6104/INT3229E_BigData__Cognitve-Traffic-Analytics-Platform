from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_monitoring_endpoint_preserves_missing_points_and_store_failure():
    from cognitive_traffic.api.monitoring import monitoring_router

    class Repository:
        def monitoring_points(self, city):
            if city == 'unavailable':
                raise RuntimeError('sentinel-secret')
            return [{'road_id': 'HN_HK_001', 'status': 'missing', 'speed_kmh': None,
                     'coordinate_kind': 'configured_anchor', 'geometry': None}]

    app = FastAPI()
    app.include_router(monitoring_router(Repository))
    with TestClient(app) as client:
        point = client.get('/monitoring/points').json()[0]
        assert point['status'] == 'missing'
        assert point['speed_kmh'] is None
        assert point['geometry'] is None
        failed = client.get('/monitoring/points?city=unavailable')
        assert failed.status_code == 503
        assert 'sentinel-secret' not in failed.text
