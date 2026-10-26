"""Authenticated Alertmanager receiver. No shell, Docker socket, or recovery capabilities."""
import hmac
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request

from cognitive_traffic.monitoring.journey_probe import probe
from cognitive_traffic.operations.oncall_agent import OnCallAgent

app = FastAPI(title='Bounded on-call runbook agent')


def token():
    value = Path(os.environ['ONCALL_TOKEN_FILE']).read_text().strip()
    if len(value) < 32:
        raise RuntimeError('oncall token must be at least 32 characters')
    return value


@app.post('/alerts')
async def alerts(request: Request, authorization: str = Header(default='')):
    secret = token()
    if not hmac.compare_digest(authorization, 'Bearer ' + secret):
        raise HTTPException(401, 'unauthorized')
    raw = await request.body()
    if len(raw) > 65536:
        raise HTTPException(413, 'payload too large')
    try:
        import json
        payload = json.loads(raw)
        batch = payload['alerts']
        if not isinstance(batch, list) or len(batch) > 20 or any(not isinstance(a, dict) for a in batch):
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise HTTPException(400, 'invalid Alertmanager payload') from None
    agent = OnCallAgent(os.getenv('INCIDENT_DB', '/state/incidents.sqlite'),
                        os.getenv('RECOVERY_QUEUE', '/state/queue'),
                        probe=lambda: probe(os.getenv('API_BASE_URL', 'http://api:8000')), token=secret)
    return {'results': [agent.handle(alert) for alert in batch]}
