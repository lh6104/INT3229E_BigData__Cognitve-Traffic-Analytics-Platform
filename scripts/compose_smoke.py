#!/usr/bin/env python3
"""Exercise the real local stack in isolated volumes/ports; never alters the user's stack."""
from __future__ import annotations

import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def ensure_stack_capacity(*, run=subprocess.run):
    memory = int(run(['docker', 'info', '--format', '{{.MemTotal}}'],
                     capture_output=True, text=True, check=True).stdout.strip())
    projects = run(['docker', 'ps', '--filter', f'label=com.docker.compose.project.working_dir={ROOT}',
                    '--format', '{{.Label "com.docker.compose.project"}}'],
                   capture_output=True, text=True, check=True).stdout.strip()
    # A concurrent app + smoke + ADG run exhausted the observed 3.69 GiB VM.
    # This floor is an acceptance safeguard, not a guarantee of enough free RAM.
    if memory < 5 * 1024**3 and projects:
        raise RuntimeError(
            'Insufficient Docker memory for a second full repository stack. '
            'Increase Docker VM memory (6 GiB allocation or more is recommended), '
            'or run make test / make test-unit until capacity is available. '
            'No existing stack will be stopped and no test stack has been created.')


def available_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def read(url, headers=None):
    with urlopen(Request(url, headers=headers or {}), timeout=10) as response:
        return json.load(response)


def eventually(check, timeout=120):
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        try:
            result = check()
            if result:
                return result
        except (OSError, ValueError, KeyError, IndexError, URLError) as exc:
            last = type(exc).__name__
        time.sleep(2)
    raise AssertionError(f'acceptance deadline exceeded ({last or "condition false"})')


class Stack:
    def __init__(self, state):
        self.project = 'cognitive-rubric-' + uuid.uuid4().hex[:10]
        self.env = dict(os.environ, COMPOSE_PROJECT_NAME=self.project, ONCALL_STATE_DIR=str(state),
                        COMPOSE_PROFILES='', COMPOSE_FILE=str(ROOT / 'docker-compose.yml'),
                        ONCALL_HOST_UID=str(os.getuid()), ONCALL_HOST_GID=str(os.getgid()))
        # Explicit isolated values also override any developer .env port preferences.
        for name in ['KAFKA_PORT', 'POSTGRES_PORT', 'REDIS_PORT', 'API_PORT', 'FRONTEND_PORT',
                     'S3_PORT', 'S3_CONSOLE_PORT', 'GRAFANA_PORT', 'PROMETHEUS_PORT',
                     'ALERTMANAGER_PORT', 'ONCALL_PORT']:
            self.env[name] = str(available_port())
        self.api = 'http://localhost:' + self.env['API_PORT']
        self.ui = 'http://localhost:' + self.env['FRONTEND_PORT']
        self.grafana = 'http://localhost:' + self.env['GRAFANA_PORT']
        self.state = state
        self.results = {}

    def compose(self, *args, capture=False):
        command = ['docker', 'compose', '-f', str(ROOT / 'docker-compose.yml'), '-p', self.project, *args]
        return subprocess.run(command, cwd=ROOT,
                              env=self.env, text=True, check=True, capture_output=capture)

    def send_fixtures(self):
        program = '''
from datetime import datetime, UTC, timedelta
from cognitive_traffic.settings import get_settings
from cognitive_traffic.streaming.producers import ContractProducer
from cognitive_traffic.streaming.topics import TRAFFIC_RAW
now = datetime.now(UTC) - timedelta(seconds=1)
base = dict(road_id='HN_HK_001',city='hanoi',source='acceptance-fixture',
            event_time=now.isoformat(),ingested_at=now.isoformat(), speed_kmh=31,
            free_flow_speed_kmh=50,dataset_id='vn-mvp-12',mode='operational')
p = ContractProducer(get_settings().kafka_bootstrap_servers)
p.send(TRAFFIC_RAW, base)
p.send(TRAFFIC_RAW, base)
p.send(TRAFFIC_RAW, dict(base,event_time=(now-timedelta(minutes=1)).isoformat(),speed_kmh=20))
p.send(TRAFFIC_RAW, dict(base,mode='replay',speed_kmh=99))
p.flush()
'''
        self.compose('exec', '-T', 'serving', 'python', '-c', program)

    def sql(self, query):
        # Read actual rendered DB user rather than assuming environment/default .env precedence.
        return self.compose('exec', '-T', 'postgres', 'sh', '-c',
                            'exec psql -U "$POSTGRES_USER" -d traffic_analytics -Atc "$1"',
                            'psql', query, capture=True).stdout.strip()

    def validate(self, browser):
        points = read(self.ui + '/api/monitoring/points')
        assert len(points) == 12 and len({r['road_id'] for r in points}) == 12
        assert sum(r['city'] == 'hanoi' for r in points) == 6
        assert all(r['status'] == 'missing' and r['geometry'] is None for r in points)
        assert read(self.api + '/traffic/current') == []
        self.send_fixtures()
        rows = eventually(lambda: read(self.ui + '/api/traffic/current'))
        assert len(rows) == 1 and rows[0]['speed_kmh'] == 31 and rows[0]['source'] == 'acceptance-fixture'
        eventually(lambda: self.sql('SELECT count(*) FROM traffic_observations') == '2')
        assert self.sql('SELECT speed_kmh FROM traffic_current') == '31'
        self.compose('restart', 'postgres')
        eventually(lambda: read(self.api + '/system/health')['status'] == 'healthy')
        assert read(self.ui + '/api/traffic/current')[0]['speed_kmh'] == 31
        if browser:
            subprocess.run(['npx', 'playwright', 'test', 'e2e/operator.spec.ts', '--workers=1',
                            '--reporter=line'], cwd=ROOT / 'frontend', check=True,
                           env=dict(self.env, TRAFFIC_BROWSER_URL=self.ui))
        else:
            with urlopen(self.ui, timeout=15) as response:
                assert response.status == 200
        print('PASS: 12 anchors; raw Kafka→normalizer→sink→PostgreSQL→API→frontend; '
              'dedup/older/replay; restart persistence', flush=True)
        self.telemetry()

    def telemetry(self):
        trace_id = uuid.uuid4().hex
        read(self.ui + '/api/monitoring/points?key=TELEMETRY_SECRET_SENTINEL',
             {'traceparent': f'00-{trace_id}-0123456789abcdef-01'})
        # Grafana datasource proxy accesses the bundled Tempo/Loki, no extra backend ports exposed.
        tempo = self.grafana + '/api/datasources/proxy/uid/tempo/api/traces/' + trace_id
        trace = eventually(lambda: read(tempo), timeout=120)
        assert trace
        query = '{service_name="traffic-api"} |= "' + trace_id + '"'
        loki = self.grafana + '/api/datasources/proxy/uid/loki/loki/api/v1/query_range?query=' + quote(query)
        logs = eventually(lambda: (read(loki).get('data', {}).get('result') or None), timeout=120)
        assert trace_id in json.dumps(logs) and 'TELEMETRY_SECRET_SENTINEL' not in json.dumps(logs)
        prometheus = 'http://localhost:' + self.env['PROMETHEUS_PORT']
        def correlated_exemplar():
            # Retry this same trace across a scrape interval; the probe also observes this route.
            read(self.ui + '/api/monitoring/points',
                 {'traceparent': f'00-{trace_id}-0123456789abcdef-01'})
            payload = read(prometheus + '/api/v1/query_exemplars?query='
                           + quote('traffic_api_request_seconds_bucket{path="/monitoring/points"}'))
            return [item for series in payload.get('data', []) for item in series.get('exemplars', [])
                    if item.get('labels', {}).get('trace_id') == trace_id]
        exemplars = eventually(correlated_exemplar, timeout=60)
        self.results['telemetry'] = {'trace_id': trace_id, 'trace_stored': True,
                                     'correlated_log_stored': True, 'secret_absent': True,
                                     'metric_exemplars': exemplars}
        self.compose('restart', 'telemetry')
        eventually(lambda: read(tempo), timeout=120)
        eventually(lambda: read(loki).get('data', {}).get('result'), timeout=120)
        print(f'PASS: stored trace {trace_id}, correlated sanitized logs, '
              'metric exemplars and telemetry restart retention', flush=True)

    def oncall(self):
        prometheus = 'http://localhost:' + self.env['PROMETHEUS_PORT']
        eventually(lambda: read(prometheus + '/api/v1/query?query=traffic_operator_journey_success')
                   ['data']['result'][0]['value'][1] == '1')
        executor_log = self.state / 'executor.log'
        with executor_log.open('w') as output:
            executor = subprocess.Popen([
                sys.executable, '-m', 'cognitive_traffic.operations.recovery_executor',
                '--project', self.project, '--queue-dir', str(self.state / 'queue'),
                '--token-file', str(self.state / 'token'), '--api-url', self.api],
                cwd=ROOT, env=self.env, stdout=output, stderr=subprocess.STDOUT)
            try:
                # The independent executor is listening before the fault occurs.
                time.sleep(2)
                assert executor.poll() is None, 'recovery executor failed to start'
                self.compose('stop', 'api')
                def requested():
                    path = self.state / 'incidents.sqlite'
                    if not path.exists():
                        return None
                    with sqlite3.connect(path) as db:
                        return db.execute("SELECT id FROM incidents WHERE requested_at IS NOT NULL").fetchone()
                incident = eventually(requested, timeout=150)[0]
                result_path = self.state / 'queue' / (incident + '.result')
                def completed():
                    if not result_path.exists():
                        return None
                    result = json.loads(result_path.read_text())
                    return result if result['state'] == 'verified' and result.get('action') == 'restart_api' else None
                result = eventually(completed, timeout=90)
                def resolved():
                    with sqlite3.connect(self.state / 'incidents.sqlite') as db:
                        db.row_factory = sqlite3.Row
                        row = db.execute("SELECT * FROM incidents WHERE id=?", (incident,)).fetchone()
                        verified = row['state'] == 'resolved' and row['verification'] == 'journey_pass'
                        return dict(row) if verified else None
                record = eventually(resolved, timeout=150)
                assert read(self.ui + '/api/traffic/current')[0]['speed_kmh'] == 31
                assert len(list((self.state / 'queue').glob('*.claim'))) == 1
                self.results['oncall'] = {'incident': record, 'executor_result': result,
                                          'executor_running_before_fault': True, 'recovery_attempts': 1}
                print(f'PASS: actual probe failure→Prometheus firing→Alertmanager delivery→incident {incident}'
                      '→allowlisted API restart→verified journey→resolved delivery', flush=True)
            finally:
                executor.terminate()
                try:
                    executor.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    executor.kill()
                    executor.wait()



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oncall', action='store_true')
    parser.add_argument('--no-browser', action='store_true', help='HTTP-only smoke; does not verify browser rendering')
    parser.add_argument('--keep', action='store_true', help='Leave isolated services running for inspection')
    parser.add_argument('--no-build', action='store_true')
    args = parser.parse_args()
    try:
        ensure_stack_capacity()
    except RuntimeError as exc:
        parser.exit(2, f'{exc}\n')
    # Docker Desktop shares the repository, but may not share host /tmp.
    state_root = ROOT / '.local'
    state_root.mkdir(exist_ok=True)
    state = Path(tempfile.mkdtemp(prefix='rubric-state-', dir=state_root))
    stack = Stack(state)
    evidence_dir = state_root / 'validation'
    evidence_dir.mkdir(exist_ok=True)
    evidence = evidence_dir / (stack.project + '.json')
    evidence.write_text(json.dumps({'project': stack.project, 'api': stack.api, 'ui': stack.ui,
                                   'grafana': stack.grafana, 'state': str(state), 'environment':
                                   {k: v for k, v in stack.env.items() if k.endswith('_PORT') or
                                    k in ('COMPOSE_PROJECT_NAME', 'ONCALL_STATE_DIR',
                                          'ONCALL_HOST_UID', 'ONCALL_HOST_GID')}}, indent=2))
    print(f'Isolated smoke metadata: {evidence}', flush=True)
    try:
        stack.compose('up', '-d', *([] if args.no_build else ['--build']), '--wait', '--wait-timeout', '240')
        stack.validate(not args.no_browser)
        if args.oncall:
            stack.oncall()
        metadata = json.loads(evidence.read_text())
        metadata.update(status='passed', browser_verified=not args.no_browser, results=stack.results)
        evidence.write_text(json.dumps(metadata, indent=2))
    except Exception:
        stack.compose('ps')
        logs = stack.compose('logs', '--no-color', '--tail', '100', capture=True)
        # Logs already redact application secrets; keep failure evidence outside repository.
        evidence.with_suffix('.log').write_text(logs.stdout)
        raise
    finally:
        if not args.keep:
            # Exact generated project and volumes only; never the user's local/default project.
            stack.compose('down', '-v', '--remove-orphans')
        else:
            print(f'Kept isolated stack. See {evidence} for ports; '
                  f'cleanup: docker compose -p {stack.project} down -v', flush=True)


if __name__ == '__main__':
    main()
