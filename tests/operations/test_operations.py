import json

from fastapi.testclient import TestClient


def test_secret_redaction_and_trace_correlation():
    from cognitive_traffic.monitoring.logging import redact
    result = redact({'error': 'https://x/?key=SENTINEL&token=SECRET', 'authorization': 'Bearer SECRET'})
    assert 'SENTINEL' not in json.dumps(result)
    assert 'SECRET' not in json.dumps(result)


def test_probe_empty_measurements_is_success():
    from cognitive_traffic.monitoring.journey_probe import semantic_success
    assert semantic_success({'status': 'healthy', 'dependencies': {'postgres': 'up'}}, [], registry_rows())
    assert not semantic_success({'status': 'degraded'}, [])
    assert not semantic_success({'status': 'healthy', 'dependencies': {'postgres': 'up'}}, {})


def test_agent_queues_only_one_recovery_and_persists_resolution(tmp_path):
    from cognitive_traffic.operations.oncall_agent import OnCallAgent
    agent = OnCallAgent(tmp_path / 'ledger.sqlite', tmp_path / 'queue', probe=lambda: False, cooldown=300)
    alert = {'status': 'firing', 'fingerprint': 'abcdef', 'startsAt': '2026-10-26T00:00:00Z',
             'labels': {'alertname': 'OperatorJourneyUnavailable', 'service': 'traffic-api'}}
    assert agent.handle(alert)['state'] == 'recovery_requested'
    assert agent.handle(alert)['state'] == 'duplicate'
    assert len(list((tmp_path / 'queue').glob('*.json'))) == 1
    agent.probe = lambda: True
    alert['status'] = 'resolved'
    assert agent.handle(alert)['state'] == 'resolved'
    assert agent.store.rows()[0]['resolved_at']


def test_agent_escalates_unsupported_and_does_not_restart_healthy(tmp_path):
    from cognitive_traffic.operations.oncall_agent import OnCallAgent
    agent = OnCallAgent(tmp_path / 'ledger.sqlite', tmp_path / 'queue', probe=lambda: True)
    alert = {'status': 'firing', 'fingerprint': 'abc', 'startsAt': 'now',
             'labels': {'alertname': 'OperatorJourneyUnavailable', 'service': 'traffic-api'}}
    assert agent.handle(alert)['state'] == 'already_healthy'
    alert['labels']['alertname'] = 'Other'
    assert agent.handle(alert)['state'] == 'unsupported'


def test_executor_rejects_nonisolated_project_and_unapproved_action(tmp_path):
    import pytest

    from cognitive_traffic.operations.recovery_executor import execute_pending
    with pytest.raises(ValueError):
        execute_pending('ADG_PRO', tmp_path)
    (tmp_path / 'bad.json').write_text(json.dumps({'action': 'shell', 'incident_id': 'abc'}))
    execute_pending('cognitive-rubric-test', tmp_path)
    assert json.loads((tmp_path / 'bad.result').read_text())['state'] == 'rejected'


def test_api_unhealthy_is_503_and_unhandled_failure_is_counted():
    from cognitive_traffic.api.main import REQUESTS, app, repository
    class Broken:
        def ping(self):
            return False
        def roads(self, city):
            raise ValueError('postgres://user:SECRET@host/db')
    old = app.dependency_overrides.copy()
    app.dependency_overrides[repository] = Broken
    try:
        client = TestClient(app, raise_server_exceptions=False)
        assert client.get('/system/health').status_code == 503
        assert client.get('/roads').status_code == 503
        assert REQUESTS.labels('GET', '/roads', '503')._value.get() >= 1
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)


def test_request_trace_log_and_metric_share_trace_id(caplog):
    import logging

    from opentelemetry import trace
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from cognitive_traffic.api.main import app, repository
    class FakeRepository:
        def current_traffic(self, city):
            return []
    exporter = InMemorySpanExporter()
    trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(exporter))
    old = app.dependency_overrides.copy()
    app.dependency_overrides[repository] = FakeRepository
    try:
        with caplog.at_level(logging.INFO):
            TestClient(app).get('/traffic/current?key=NEVER_LOG_SENTINEL')
        span = [s for s in exporter.get_finished_spans() if s.name == 'GET /traffic/current'][-1]
        trace_id = f'{span.context.trace_id:032x}'
        assert trace_id in caplog.text
        metrics = TestClient(app).get('/metrics').text
        assert f'trace_id="{trace_id}"' in metrics
        assert 'NEVER_LOG_SENTINEL' not in caplog.text
        assert 'NEVER_LOG_SENTINEL' not in str(span.attributes)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)


def test_authenticated_receiver_rejects_bad_shape_and_missing_auth(tmp_path, monkeypatch):
    from cognitive_traffic.operations.alert_receiver import app
    path = tmp_path / 'token'
    path.write_text('a' * 64)
    monkeypatch.setenv('ONCALL_TOKEN_FILE', str(path))
    client = TestClient(app)
    assert client.post('/alerts', json={'alerts': []}).status_code == 401
    assert client.post('/alerts', json={'alerts': 42},
                       headers={'authorization': 'Bearer ' + 'a' * 64}).status_code == 400


def test_executor_authenticates_caps_attempts_and_verifies_journey(tmp_path, monkeypatch):
    import time
    from types import SimpleNamespace

    from cognitive_traffic.operations import recovery_executor as executor
    from cognitive_traffic.operations.oncall_agent import signature
    calls = []
    monkeypatch.setattr(executor.subprocess, 'run', lambda command, **kw:
                        (calls.append(command) or SimpleNamespace(returncode=0)))
    probes = iter([False, True])
    monkeypatch.setattr(executor, 'probe', lambda url: next(probes))
    payload = {'incident_id': 'a' * 64, 'action': 'restart_api', 'created_at': time.time()}
    authorize_request(tmp_path.parent / 'incidents.sqlite', payload)
    request = tmp_path / 'good.json'
    request.write_text(json.dumps({'payload': payload, 'signature': signature(payload, 'a' * 64)}))
    executor.execute_pending('cognitive-rubric-test', tmp_path, 'a' * 64)
    (tmp_path / 'duplicate.json').write_text(request.read_text())
    executor.execute_pending('cognitive-rubric-test', tmp_path, 'a' * 64)
    assert calls == [['docker', 'compose', '-p', 'cognitive-rubric-test', 'restart', 'api']]
    assert json.loads(request.with_suffix('.result').read_text())['state'] == 'verified'


def test_agent_invalid_labels_does_not_crash(tmp_path):
    from cognitive_traffic.operations.oncall_agent import OnCallAgent
    agent = OnCallAgent(tmp_path / 'ledger.sqlite', tmp_path / 'queue', probe=lambda: False)
    assert agent.handle({'labels': 42})['state'] == 'invalid'


def test_unhandled_request_failure_is_500_with_redacted_span(caplog):
    from opentelemetry import trace
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from cognitive_traffic.api.main import REQUESTS, app, repository
    exporter = InMemorySpanExporter()
    trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(exporter))
    def broken_dependency():
        raise RuntimeError('https://provider/?key=NEVER_LOG_EXCEPTION')
    old = app.dependency_overrides.copy()
    app.dependency_overrides[repository] = broken_dependency
    try:
        client = TestClient(app, raise_server_exceptions=False)
        assert client.get('/roads').status_code == 500
        assert REQUESTS.labels('GET', '/roads', '500')._value.get() >= 1
        span = [s for s in exporter.get_finished_spans() if s.name == 'GET /roads'][-1]
        assert not span.events
        assert 'NEVER_LOG_EXCEPTION' not in caplog.text
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)


def test_provider_exception_does_not_log_secret(caplog):
    import logging

    import requests

    from cognitive_traffic.ingestion.traffic import run_once
    class Session:
        def get(self, *args, **kwargs):
            raise requests.HTTPError('https://provider/?key=PROVIDER_SECRET_SENTINEL')
    class Producer:
        def flush(self):
            pass
    with caplog.at_level(logging.WARNING):
        assert run_once(Session(), Producer(), [{'segment_id': 'x', 'lat': 1, 'lon': 2}], 'key') == 0
    assert 'PROVIDER_SECRET_SENTINEL' not in caplog.text
    assert 'HTTPError' in caplog.text
    assert 'https://provider/' not in caplog.text


def registry_rows():
    from pathlib import Path

    from cognitive_traffic.monitoring.registry import load_monitoring_points
    return [dict(road_id=p.point_id, city=p.city, name=p.point_id, category='monitoring_point',
                 latitude=p.lat, longitude=p.lon, coordinate_kind='configured_anchor', geometry=None,
                 status='missing', event_time=None, speed_kmh=None, free_flow_speed_kmh=None,
                 confidence=None, source=None, dataset_id=None, mode=None)
            for p in load_monitoring_points(Path('configs/sources.yaml'))]


def test_probe_checks_actual_ui_registry_semantics():
    from copy import deepcopy

    from cognitive_traffic.monitoring.journey_probe import semantic_success
    health = {'status': 'healthy', 'dependencies': {'postgres': 'up'}}
    rows = registry_rows()
    assert semantic_success(health, [], rows)
    for field, value in [('road_id', 'unknown'), ('city', 'invalidcity'), ('latitude', 900),
                         ('status', 'unknown'), ('speed_kmh', 42)]:
        broken = deepcopy(rows)
        broken[0][field] = value
        assert not semantic_success(health, [], broken), field
    assert not semantic_success(health, [], rows[:-1])
    assert not semantic_success(health, [], [rows[0]] * 12)


def test_executor_healthy_preflight_does_not_restart(tmp_path, monkeypatch):
    import time

    from cognitive_traffic.operations import recovery_executor as executor
    from cognitive_traffic.operations.oncall_agent import signature
    monkeypatch.setattr(executor, 'probe', lambda _: True)
    def forbidden(*args, **kwargs):
        raise AssertionError('a recovered API must not be restarted')
    monkeypatch.setattr(executor.subprocess, 'run', forbidden)
    payload = {'incident_id': 'b' * 64, 'action': 'restart_api', 'created_at': time.time()}
    authorize_request(tmp_path.parent / 'incidents.sqlite', payload)
    request = tmp_path / 'healthy.json'
    request.write_text(json.dumps({'payload': payload, 'signature': signature(payload, 'a' * 64)}))
    executor.execute_pending('cognitive-rubric-test', tmp_path, 'a' * 64)
    assert json.loads(request.with_suffix('.result').read_text())['state'] == 'already_healthy'


def test_unknown_resolution_is_not_claimed_as_resolved(tmp_path):
    from cognitive_traffic.operations.oncall_agent import OnCallAgent
    agent = OnCallAgent(tmp_path / 'incidents.sqlite', tmp_path / 'queue', probe=lambda: True)
    alert = {'status': 'resolved', 'fingerprint': 'unknown', 'startsAt': 'now',
             'labels': {'alertname': 'OperatorJourneyUnavailable', 'service': 'traffic-api'}}
    assert agent.handle(alert)['state'] == 'unknown_resolution'


def test_failed_resolved_verification_does_not_set_resolved_timestamp(tmp_path):
    from cognitive_traffic.operations.oncall_agent import OnCallAgent
    agent = OnCallAgent(tmp_path / 'incidents.sqlite', tmp_path / 'queue', probe=lambda: False)
    alert = {'status': 'firing', 'fingerprint': 'unknown', 'startsAt': 'now',
             'labels': {'alertname': 'OperatorJourneyUnavailable', 'service': 'traffic-api'}}
    agent.handle(alert)
    alert['status'] = 'resolved'
    assert agent.handle(alert)['state'] == 'escalated'
    assert agent.store.rows()[0]['resolved_at'] is None


def test_executor_rejects_signed_request_without_committed_incident(tmp_path, monkeypatch):
    import time

    from cognitive_traffic.operations import recovery_executor as executor
    from cognitive_traffic.operations.oncall_agent import signature
    def forbidden(*args, **kwargs):
        raise AssertionError('uncommitted request must never execute')
    monkeypatch.setattr(executor, 'probe', lambda _: False)
    monkeypatch.setattr(executor.subprocess, 'run', forbidden)
    queue = tmp_path / 'queue'
    queue.mkdir()
    payload = {'incident_id': 'c' * 64, 'action': 'restart_api', 'created_at': time.time()}
    request = queue / 'bad.json'
    request.write_text(json.dumps({'payload': payload, 'signature': signature(payload, 'a' * 64)}))
    executor.execute_pending('cognitive-rubric-test', queue, 'a' * 64)
    assert json.loads(request.with_suffix('.result').read_text())['state'] == 'rejected'


def authorize_request(ledger, payload):
    from cognitive_traffic.operations.incident_store import IncidentStore
    store = IncidentStore(ledger)
    with store.connect() as db:
        db.execute('INSERT OR REPLACE INTO incidents VALUES (?,?,?,?,?,?,?,?,?)',
                   (payload['incident_id'], 'test', 'test', payload['created_at'], 'recovery_requested',
                    'test', payload['created_at'], None, None))


def test_uvicorn_unhandled_exception_does_not_export_secret(tmp_path):
    import os
    import socket
    import subprocess
    import sys
    import time
    from urllib.error import HTTPError
    from urllib.request import urlopen
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    code = f"""
import uvicorn
from cognitive_traffic.api.main import app, repository
def broken():
    raise RuntimeError('https://provider/?key=UVICORN_SECRET_SENTINEL')
app.dependency_overrides[repository] = broken
uvicorn.run(app, host='127.0.0.1', port={port})
"""
    log = tmp_path / 'server.log'
    with log.open('w') as output:
        env = dict(os.environ, PYTHONPATH='src')
        process = subprocess.Popen([sys.executable, '-c', code], stdout=output, stderr=output, env=env)
        try:
            for _ in range(100):
                try:
                    urlopen(f'http://127.0.0.1:{port}/roads?key=ACCESS_SECRET_SENTINEL', timeout=0.2)
                except HTTPError as exc:
                    assert exc.code == 500
                    break
                except OSError:
                    time.sleep(0.05)
            else:
                raise AssertionError('server did not start')
        finally:
            process.terminate()
            process.wait(timeout=5)
    assert 'UVICORN_SECRET_SENTINEL' not in log.read_text()
    assert 'ACCESS_SECRET_SENTINEL' not in log.read_text()
    assert 'request_failed' in log.read_text()


def test_queue_visibility_only_after_committed_incident(tmp_path, monkeypatch):
    import pytest

    from cognitive_traffic.operations import oncall_agent
    real_replace = oncall_agent.os.replace
    def fail_after_publish(source, destination):
        real_replace(source, destination)
        raise OSError('simulated process failure after queue publication')
    monkeypatch.setattr(oncall_agent.os, 'replace', fail_after_publish)
    agent = oncall_agent.OnCallAgent(tmp_path / 'incidents.sqlite', tmp_path / 'queue', probe=lambda: False)
    with pytest.raises(OSError):
        agent.handle({'status': 'firing', 'fingerprint': 'crash', 'startsAt': 'now',
                      'labels': {'alertname': 'OperatorJourneyUnavailable', 'service': 'traffic-api'}})
    assert len(list((tmp_path / 'queue').glob('*.json'))) == 1
    assert agent.store.rows()[0]['state'] == 'recovery_requested'


def test_committed_request_republished_on_retry_after_publication_failure(tmp_path, monkeypatch):
    import pytest

    from cognitive_traffic.operations import oncall_agent
    agent = oncall_agent.OnCallAgent(tmp_path / 'incidents.sqlite', tmp_path / 'queue', probe=lambda: False)
    alert = {'status': 'firing', 'fingerprint': 'publish-failed', 'startsAt': 'now',
             'labels': {'alertname': 'OperatorJourneyUnavailable', 'service': 'traffic-api'}}
    real_replace = oncall_agent.os.replace
    def fail_before_publish(*args):
        raise OSError('disk temporarily unavailable')
    monkeypatch.setattr(oncall_agent.os, 'replace', fail_before_publish)
    with pytest.raises(OSError):
        agent.handle(alert)
    incident = agent.store.rows()[0]
    assert incident['state'] == 'recovery_requested'
    assert not list((tmp_path / 'queue').glob('*.json'))
    monkeypatch.setattr(oncall_agent.os, 'replace', real_replace)
    monkeypatch.setattr(oncall_agent.time, 'time', lambda: incident['requested_at'] + 5)
    assert agent.handle(alert)['state'] == 'recovery_requested'
    envelope = json.loads((tmp_path / 'queue' / (incident['id'] + '.json')).read_text())
    assert envelope['payload']['created_at'] == incident['requested_at']
    assert agent.handle(alert)['state'] == 'duplicate'


def test_missing_request_retry_does_not_renew_expired_authorization(tmp_path, monkeypatch):
    from cognitive_traffic.operations import oncall_agent
    agent = oncall_agent.OnCallAgent(tmp_path / 'incidents.sqlite', tmp_path / 'queue', probe=lambda: False)
    alert = {'status': 'firing', 'fingerprint': 'expired', 'startsAt': 'now',
             'labels': {'alertname': 'OperatorJourneyUnavailable', 'service': 'traffic-api'}}
    agent.handle(alert)
    incident = agent.store.rows()[0]
    request = tmp_path / 'queue' / (incident['id'] + '.json')
    request.unlink()
    monkeypatch.setattr(oncall_agent.time, 'time', lambda: incident['requested_at'] + 601)
    assert agent.handle(alert)['state'] == 'escalated'
    assert not request.exists()
    row = agent.store.rows()[0]
    assert row['state'] == 'escalated'
    assert row['requested_at'] == incident['requested_at']


def test_missing_request_retry_respects_existing_executor_claim(tmp_path):
    from cognitive_traffic.operations.oncall_agent import OnCallAgent
    agent = OnCallAgent(tmp_path / 'incidents.sqlite', tmp_path / 'queue', probe=lambda: False)
    alert = {'status': 'firing', 'fingerprint': 'claimed', 'startsAt': 'now',
             'labels': {'alertname': 'OperatorJourneyUnavailable', 'service': 'traffic-api'}}
    agent.handle(alert)
    incident = agent.store.rows()[0]
    request = tmp_path / 'queue' / (incident['id'] + '.json')
    request.unlink()
    request.with_suffix('.claim').touch()
    assert agent.handle(alert)['state'] == 'duplicate'
    assert not request.exists()


def test_executor_failed_recovery_is_terminal_in_incident_ledger(tmp_path, monkeypatch):
    import subprocess
    import time
    from types import SimpleNamespace

    from cognitive_traffic.operations import recovery_executor as executor
    from cognitive_traffic.operations.incident_store import IncidentStore
    from cognitive_traffic.operations.oncall_agent import signature

    for outcome, reason in [('nonzero', 'restart_failed'), ('timeout', 'restart_timeout'),
                            ('unverified', 'journey_verification_failed')]:
        state = tmp_path / outcome
        queue = state / 'queue'
        queue.mkdir(parents=True)
        payload = {'incident_id': 'd' * 64, 'action': 'restart_api', 'created_at': time.time()}
        authorize_request(state / 'incidents.sqlite', payload)
        request = queue / 'request.json'
        request.write_text(json.dumps({'payload': payload, 'signature': signature(payload, 'a' * 64)}))
        calls = []
        def restart(command, calls=calls, outcome=outcome, **kwargs):
            calls.append(command)
            if outcome == 'timeout':
                raise subprocess.TimeoutExpired(command, 60)
            return SimpleNamespace(returncode=1 if outcome == 'nonzero' else 0)
        monkeypatch.setattr(executor.subprocess, 'run', restart)
        monkeypatch.setattr(executor, 'probe', lambda _: False)
        monkeypatch.setattr(executor.time, 'sleep', lambda _: None)
        executor.execute_pending('cognitive-rubric-test', queue, 'a' * 64)
        row = IncidentStore(state / 'incidents.sqlite').rows()[0]
        assert (row['state'], row['verification'], row['resolved_at']) == ('escalated', reason, None)
        assert json.loads(request.with_suffix('.result').read_text())['state'] == 'escalated'
        # Another filename carrying the same signed request cannot cause another attempt.
        (queue / 'duplicate.json').write_text(request.read_text())
        executor.execute_pending('cognitive-rubric-test', queue, 'a' * 64)
        assert len(calls) == 1


def test_executor_expired_signed_committed_request_escalates_without_execution(tmp_path, monkeypatch):
    import time

    from cognitive_traffic.operations import recovery_executor as executor
    from cognitive_traffic.operations.incident_store import IncidentStore
    from cognitive_traffic.operations.oncall_agent import signature

    queue = tmp_path / 'queue'
    queue.mkdir()
    payload = {'incident_id': 'e' * 64, 'action': 'restart_api', 'created_at': time.time() - 601}
    authorize_request(tmp_path / 'incidents.sqlite', payload)
    request = queue / 'expired.json'
    request.write_text(json.dumps({'payload': payload, 'signature': signature(payload, 'a' * 64)}))
    def forbidden(*args, **kwargs):
        raise AssertionError('expired authorization must not probe or execute')
    monkeypatch.setattr(executor, 'probe', forbidden)
    monkeypatch.setattr(executor.subprocess, 'run', forbidden)
    executor.execute_pending('cognitive-rubric-test', queue, 'a' * 64)
    row = IncidentStore(tmp_path / 'incidents.sqlite').rows()[0]
    assert (row['state'], row['verification'], row['resolved_at']) == (
        'escalated', 'recovery_request_expired', None)
    assert json.loads(request.with_suffix('.result').read_text())['state'] == 'escalated'
    assert not list(queue.glob('*.claim'))


def test_executor_forged_expired_request_cannot_escalate_incident(tmp_path, monkeypatch):
    import time

    from cognitive_traffic.operations import recovery_executor as executor
    from cognitive_traffic.operations.incident_store import IncidentStore
    from cognitive_traffic.operations.oncall_agent import signature

    queue = tmp_path / 'queue'
    queue.mkdir()
    payload = {'incident_id': 'f' * 64, 'action': 'restart_api', 'created_at': time.time() - 601}
    authorize_request(tmp_path / 'incidents.sqlite', payload)
    before = IncidentStore(tmp_path / 'incidents.sqlite').rows()
    request = queue / 'forged.json'
    request.write_text(json.dumps({'payload': payload, 'signature': signature(payload, 'wrong' * 16)}))
    def forbidden(*args, **kwargs):
        raise AssertionError('forged request must not execute')
    monkeypatch.setattr(executor.subprocess, 'run', forbidden)
    executor.execute_pending('cognitive-rubric-test', queue, 'a' * 64)
    assert IncidentStore(tmp_path / 'incidents.sqlite').rows() == before
    assert json.loads(request.with_suffix('.result').read_text())['state'] == 'rejected'


def test_executor_failure_preserves_concurrent_incident_resolution(tmp_path, monkeypatch):
    import sqlite3
    import time
    from types import SimpleNamespace

    from cognitive_traffic.operations import recovery_executor as executor
    from cognitive_traffic.operations.incident_store import IncidentStore
    from cognitive_traffic.operations.oncall_agent import signature

    queue = tmp_path / 'queue'
    queue.mkdir()
    ledger = tmp_path / 'incidents.sqlite'
    payload = {'incident_id': 'a' * 64, 'action': 'restart_api', 'created_at': time.time()}
    authorize_request(ledger, payload)
    (queue / 'request.json').write_text(json.dumps({'payload': payload, 'signature': signature(payload, 'a' * 64)}))
    def failed_restart_with_concurrent_resolution(*args, **kwargs):
        with sqlite3.connect(ledger) as db:
            db.execute("UPDATE incidents SET state='resolved', verification='journey_pass', resolved_at=123")
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(executor, 'probe', lambda _: False)
    monkeypatch.setattr(executor.subprocess, 'run', failed_restart_with_concurrent_resolution)
    executor.execute_pending('cognitive-rubric-test', queue, 'a' * 64)
    row = IncidentStore(ledger).rows()[0]
    assert (row['state'], row['verification'], row['resolved_at']) == ('resolved', 'journey_pass', 123)
