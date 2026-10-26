#!/usr/bin/env python3
"""Run the full suite against an explicit DSN or an isolated disposable PostgreSQL."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_tests(env=None, *, run=subprocess.run):
    environment = dict(os.environ if env is None else env)
    container = None
    status = 0

    def command(args, *, capture=False, timeout=None):
        return run(args, cwd=ROOT, env=environment, text=True, capture_output=capture, timeout=timeout)

    def checked(args, *, capture=False, timeout=None):
        result = command(args, capture=capture, timeout=timeout)
        if result.returncode:
            raise subprocess.CalledProcessError(result.returncode, args)
        return result

    try:
        if not environment.get('TRAFFIC_TEST_DSN', '').strip():
            checked(['docker', 'info'], capture=True, timeout=30)
            container = 'cognitive-tests-' + uuid.uuid4().hex
            password = uuid.uuid4().hex
            print('Starting an isolated disposable PostgreSQL for the full test suite.', flush=True)
            checked(['docker', 'run', '-d', '--name', container,
                     '-p', '127.0.0.1::5432', '-e', 'POSTGRES_DB=traffic_test',
                     '-e', 'POSTGRES_USER=postgres', '-e', f'POSTGRES_PASSWORD={password}',
                     'postgres:16-alpine'], capture=True, timeout=180)
            ports = json.loads(checked(['docker', 'inspect', '--format',
                                       '{{json .NetworkSettings.Ports}}', container],
                                      capture=True, timeout=30).stdout)
            port = ports['5432/tcp'][0]['HostPort']
            environment['TRAFFIC_TEST_DSN'] = f'postgresql://postgres:{password}@127.0.0.1:{port}/traffic_test'
            deadline = time.monotonic() + 60
            while True:
                ready = command(['docker', 'exec', container, 'pg_isready', '-h', '127.0.0.1',
                                 '-U', 'postgres', '-d', 'traffic_test'], capture=True, timeout=10)
                if ready.returncode == 0:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError('PostgreSQL did not become ready within 60 seconds')
                time.sleep(1)
        checked([sys.executable, '-m', 'pytest'])
        checked(['node', '--test', *[str(path.relative_to(ROOT))
                                   for path in sorted((ROOT / 'frontend/tests').glob('*.test.mjs'))]])
    except subprocess.CalledProcessError as exc:
        status = exc.returncode if exc.returncode > 0 else 1
        print('Full test run failed. Docker must be running, or provide an isolated TRAFFIC_TEST_DSN; '
              'Python and Node tests must both pass.', file=sys.stderr)
    except (OSError, ValueError, KeyError, IndexError, subprocess.TimeoutExpired) as exc:
        status = 1
        print(f'Full test run could not complete ({type(exc).__name__}). '
              'Install/start Docker or provide an isolated TRAFFIC_TEST_DSN; '
              'ensure Node is available.', file=sys.stderr)
    finally:
        if container:
            try:
                cleanup = command(['docker', 'rm', '-f', '-v', container], capture=True, timeout=30)
                if cleanup.returncode:
                    raise OSError('container removal failed')
            except (OSError, subprocess.TimeoutExpired):
                print(f'Cleanup failed; remove only the test resource: docker rm -f -v {container}',
                      file=sys.stderr)
                status = status or 1
    return status


if __name__ == '__main__':
    raise SystemExit(run_tests())
