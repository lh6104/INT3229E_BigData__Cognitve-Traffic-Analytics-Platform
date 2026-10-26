"""The full test entry point cannot report success after omitting its database checks."""
import importlib.util
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def runner():
    path = Path('scripts/run_tests.py')
    assert path.exists(), 'Full-suite runner must provision an isolated database or require an explicit DSN'
    spec = importlib.util.spec_from_file_location('traffic_test_runner', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Commands:
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        code = self.fail(command) if self.fail else 0
        output = '{"5432/tcp":[{"HostIp":"127.0.0.1","HostPort":"49123"}]}'
        return subprocess.CompletedProcess(command, code, stdout=output, stderr='')


def test_explicit_database_runs_both_suites_without_docker(runner):
    commands = Commands()
    assert runner.run_tests({'TRAFFIC_TEST_DSN': 'postgresql://explicit/test'}, run=commands) == 0
    assert all(call[0][0] != 'docker' for call in commands.calls)
    assert any('-m' in cmd and 'pytest' in cmd for cmd, _ in commands.calls)
    assert any(cmd[:2] == ['node', '--test'] for cmd, _ in commands.calls)
    assert all(options['env']['TRAFFIC_TEST_DSN'] == 'postgresql://explicit/test'
               for _, options in commands.calls)


def test_missing_docker_fails_before_pytest_with_actionable_message(runner, capsys):
    def missing(*args, **kwargs):
        raise FileNotFoundError('docker')

    assert runner.run_tests({}, run=missing) != 0
    assert 'TRAFFIC_TEST_DSN' in capsys.readouterr().err


@pytest.mark.parametrize('failed_suite,exit_code', [('pytest', 5), ('node', 7)])
def test_provisioned_database_is_cleaned_after_test_failure(runner, failed_suite, exit_code):
    commands = Commands(lambda cmd: exit_code if failed_suite in cmd else 0)
    assert runner.run_tests({}, run=commands) == exit_code
    created = next(cmd for cmd, _ in commands.calls if cmd[:2] == ['docker', 'run'])
    name = created[created.index('--name') + 1]
    assert name.startswith('cognitive-tests-')
    assert '127.0.0.1::5432' in created
    assert commands.calls[-1][0] == ['docker', 'rm', '-f', '-v', name]
    pytest_env = next(options['env'] for cmd, options in commands.calls if 'pytest' in cmd)
    assert '@127.0.0.1:49123/' in pytest_env['TRAFFIC_TEST_DSN']


def test_cleanup_failure_cannot_report_success(runner):
    commands = Commands(lambda cmd: 1 if cmd[:2] == ['docker', 'rm'] else 0)
    assert runner.run_tests({}, run=commands) != 0


def test_failed_container_start_still_attempts_cleanup(runner):
    commands = Commands(lambda cmd: 23 if cmd[:2] == ['docker', 'run'] else 0)
    assert runner.run_tests({}, run=commands) == 23
    assert commands.calls[-1][0][:4] == ['docker', 'rm', '-f', '-v']
    assert all('pytest' not in cmd for cmd, _ in commands.calls)


def test_successful_full_run_removes_only_its_disposable_resource(runner):
    commands = Commands()
    assert runner.run_tests({}, run=commands) == 0
    assert any(cmd[:2] == ['node', '--test'] for cmd, _ in commands.calls)
    assert commands.calls[-1][0][:4] == ['docker', 'rm', '-f', '-v']
    assert len(commands.calls[-1][0]) == 5


def test_unready_database_fails_before_tests_and_is_removed(runner, monkeypatch):
    commands = Commands(lambda cmd: 1 if 'pg_isready' in cmd else 0)
    ticks = iter([0, 61])
    monkeypatch.setattr(runner.time, 'monotonic', lambda: next(ticks))
    assert runner.run_tests({}, run=commands) != 0
    assert all('pytest' not in cmd for cmd, _ in commands.calls)
    assert commands.calls[-1][0][:4] == ['docker', 'rm', '-f', '-v']
