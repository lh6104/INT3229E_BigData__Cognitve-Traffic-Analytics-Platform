"""Offline safety and shape guard for the disposable Render contest demo."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_render_demo_blueprint_is_three_resources_only():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text())
    services = {service["name"]: service for service in blueprint["services"]}
    database, = blueprint["databases"]
    assert set(services) == {"traffic-api", "traffic-dashboard"}
    assert database["name"] == "traffic-demo-db"
    assert database["plan"] == "free"
    assert database["ipAllowList"] == []
    assert len({service["region"] for service in services.values()} | {database["region"]}) == 1
    assert all(service["type"] == "web" and service["runtime"] == "docker"
               and service["plan"] == "free" for service in services.values())

    api = services["traffic-api"]
    assert api["dockerfilePath"] == "infra/docker/api.Dockerfile"
    assert api["dockerContext"] == "."
    assert api["healthCheckPath"] == "/system/health"
    assert "dockerCommand" not in api  # Use the image CMD; Render must not re-tokenize a shell chain.
    dockerfile = (ROOT / api["dockerfilePath"]).read_text()
    assert "CMD [\"/app/api-entrypoint.sh\"]" in dockerfile
    entrypoint = (ROOT / "infra/docker/api-entrypoint.sh").read_text()
    assert "python -m cognitive_traffic.storage.bootstrap" in entrypoint
    assert "exec uvicorn cognitive_traffic.api.main:app" in entrypoint
    assert '--port "${PORT:-10000}"' in entrypoint
    assert api["envVars"][-1] == {"key": "POSTGRES_DSN", "fromDatabase": {
        "name": "traffic-demo-db", "property": "connectionString"}}

    dashboard = services["traffic-dashboard"]
    assert dashboard["dockerfilePath"] == "infra/docker/frontend.Dockerfile"
    assert dashboard["dockerContext"] == "."
    assert dashboard["envVars"] == [{"key": "API_UPSTREAM", "fromService": {
        "name": "traffic-api", "type": "web", "envVarKey": "RENDER_EXTERNAL_HOSTNAME"}}]
    assert all("POLL" not in variable["key"] and "API_KEY" not in variable["key"]
               for service in services.values() for variable in service.get("envVars", []))
