"""Explicit host-only executor: fixed API restart in an isolated assessment project."""
import argparse
import hmac
import json
import math
import os
import re
import sqlite3
import subprocess
import time
from pathlib import Path

from cognitive_traffic.monitoring.journey_probe import probe
from cognitive_traffic.operations.oncall_agent import signature


def escalate(ledger, payload, reason):
    # Never overwrite a concurrent resolution or a different authorization lease.
    with sqlite3.connect(f'file:{ledger}?mode=rw', uri=True) as db:
        db.execute('''UPDATE incidents SET state='escalated', verification=?, resolved_at=NULL
                      WHERE id=? AND state='recovery_requested' AND requested_at=?''',
                   (reason, payload['incident_id'], payload['created_at']))


def execute_pending(project, queue, token='', api_url='http://localhost:8000'):
    if not re.fullmatch(r'cognitive-rubric-[a-z0-9-]{1,40}', project):
        raise ValueError('only cognitive-rubric-* isolated project names are permitted')
    queue = Path(queue)
    for path in queue.glob('*.json'):
        result_path = path.with_suffix('.result')
        if result_path.exists():
            continue
        state = 'rejected'
        try:
            if path.is_symlink() or path.stat().st_size > 4096:
                raise ValueError()
            envelope = json.loads(path.read_text())
            payload = envelope['payload']
            if (len(token) < 32 or not hmac.compare_digest(envelope['signature'], signature(payload, token))
                    or payload['action'] != 'restart_api'
                    or not re.fullmatch(r'[0-9a-f]{64}', payload['incident_id'])
                    or not isinstance(payload['created_at'], (int, float))
                    or isinstance(payload['created_at'], bool)
                    or not math.isfinite(payload['created_at'])
                    or payload['created_at'] > time.time()):
                raise ValueError()
            ledger = queue.parent / 'incidents.sqlite'
            with sqlite3.connect(f'file:{ledger}?mode=ro', uri=True) as db:
                incident = db.execute('SELECT state,requested_at FROM incidents WHERE id=?',
                                      (payload['incident_id'],)).fetchone()
            if incident != ('recovery_requested', payload['created_at']):
                raise ValueError()
            if time.time() - payload['created_at'] > 600:
                escalate(ledger, payload, 'recovery_request_expired')
                result_path.write_text(json.dumps({'state': 'escalated', 'at': time.time(),
                                                  'verification': 'recovery_request_expired'}))
                continue
            # Durable claim BEFORE subprocess: crash cannot cause repeated restart on next invocation.
            claim = queue / (payload['incident_id'] + '.claim')
            try:
                claim_fd = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                result_path.write_text(json.dumps({'state': 'duplicate', 'at': time.time()}))
                continue
            with os.fdopen(claim_fd, 'w') as target:
                target.write(json.dumps({'state': 'claimed', 'at': time.time()}))
            result_path.write_text(json.dumps({'state': 'claimed', 'at': time.time()}))
            if probe(api_url):
                result_path.write_text(json.dumps({'state': 'already_healthy', 'at': time.time(), 'action': 'none'}))
                continue
            state = 'escalated'
            reason = 'restart_failed'
            try:
                completed = subprocess.run(['docker', 'compose', '-p', project, 'restart', 'api'],
                                           timeout=60, capture_output=True, check=False)
                if completed.returncode == 0:
                    reason = 'journey_verification_failed'
                    for _ in range(12):
                        if probe(api_url):
                            state = 'verified'
                            break
                        time.sleep(2)
            except subprocess.TimeoutExpired:
                reason = 'restart_timeout'
            except OSError:
                pass
            if state == 'escalated':
                escalate(ledger, payload, reason)
        except (ValueError, KeyError, TypeError, OSError, sqlite3.Error, subprocess.TimeoutExpired):
            pass
        result_path.write_text(json.dumps({'state': state, 'at': time.time(), 'action': 'restart_api'}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--queue-dir', required=True)
    parser.add_argument('--token-file', required=True)
    parser.add_argument('--api-url', default='http://localhost:8000')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    secret = Path(args.token_file).read_text().strip()
    while True:
        execute_pending(args.project, args.queue_dir, secret, args.api_url)
        if args.once:
            return
        time.sleep(2)


if __name__ == '__main__':
    main()
