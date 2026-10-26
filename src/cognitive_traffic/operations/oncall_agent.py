"""Transparent deterministic runbook agent, with one recovery attempt per incident."""
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

from cognitive_traffic.operations.incident_store import IncidentStore


def signature(payload, token):
    return hmac.new(token.encode(), json.dumps(payload, sort_keys=True).encode(), hashlib.sha256).hexdigest()


class OnCallAgent:
    def __init__(self, ledger, queue, probe, cooldown=300, token='test-only'):
        self.store = IncidentStore(ledger)
        self.queue = Path(queue)
        self.queue.mkdir(parents=True, exist_ok=True)
        self.probe, self.cooldown, self.token = probe, cooldown, token

    def _publish(self, identity, requested_at):
        payload = {'incident_id': identity, 'action': 'restart_api', 'created_at': requested_at}
        envelope = {'payload': payload, 'signature': signature(payload, self.token)}
        temporary = self.queue / f'{identity}.tmp'
        temporary.write_text(json.dumps(envelope))
        os.replace(temporary, self.queue / f'{identity}.json')

    def handle(self, alert):
        labels = alert.get('labels', {})
        if not isinstance(labels, dict):
            return {'state': 'invalid'}
        if labels.get('alertname') != 'OperatorJourneyUnavailable' or labels.get('service') != 'traffic-api':
            return {'state': 'unsupported'}
        fingerprint, start = alert.get('fingerprint'), alert.get('startsAt')
        if not isinstance(fingerprint, str) or not fingerprint or not isinstance(start, str):
            return {'state': 'invalid'}
        identity = hashlib.sha256(f'{fingerprint}:{start}'.encode()).hexdigest()
        now = time.time()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if alert.get('status') == 'resolved':
                if not db.execute('SELECT id FROM incidents WHERE id=?', (identity,)).fetchone():
                    return {'state': 'unknown_resolution'}
                verified = self.probe()
                db.execute('UPDATE incidents SET resolved_at=?,state=?,verification=? WHERE id=?',
                           (now if verified else None, 'resolved' if verified else 'escalated',
                            'journey_pass' if verified else 'resolved_alert_but_journey_failed', identity))
                return {'state': 'resolved' if verified else 'escalated'}
            if alert.get('status') != 'firing':
                return {'state': 'invalid'}
            existing = db.execute('SELECT state,requested_at FROM incidents WHERE id=?', (identity,)).fetchone()
            if existing:
                request_missing = not (self.queue / f'{identity}.json').exists()
                unclaimed = not (self.queue / f'{identity}.claim').exists()
                if existing['state'] == 'recovery_requested' and request_missing and unclaimed:
                    requested_at = existing['requested_at']
                    if requested_at is None or not 0 <= now - requested_at <= 600:
                        db.execute('UPDATE incidents SET state=?,diagnosis=? WHERE id=?',
                                   ('escalated', 'recovery_request_expired', identity))
                        return {'state': 'escalated', 'incident_id': identity}
                    # Reuse committed authorization; a failed publish must never renew its lease.
                    self._publish(identity, requested_at)
                    return {'state': 'recovery_requested', 'incident_id': identity}
                return {'state': 'duplicate'}
            healthy = self.probe()
            recent = db.execute('SELECT id FROM incidents WHERE requested_at>?', (now - self.cooldown,)).fetchone()
            state = 'already_healthy' if healthy else 'escalated' if recent else 'recovery_requested'
            diagnosis = 'journey_pass' if healthy else 'semantic_operator_read_failed'
            db.execute('INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?)',
                       (identity, fingerprint[:256], start[:128], now, state, diagnosis,
                        now if state == 'recovery_requested' else None, None, None))
            # Commit authorization before making a signed request visible to the executor.
            db.commit()
            if state == 'recovery_requested':
                self._publish(identity, now)
            return {'state': state, 'incident_id': identity}
