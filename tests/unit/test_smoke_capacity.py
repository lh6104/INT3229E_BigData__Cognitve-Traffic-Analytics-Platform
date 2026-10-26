"""Do not launch another heavy stack into the observed undersized shared VM."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def smoke_module():
    spec = importlib.util.spec_from_file_location('traffic_compose_smoke', Path('scripts/compose_smoke.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def docker_snapshot(memory_gib, projects):
    def run(command, **kwargs):
        if command[:2] == ['docker', 'info']:
            return SimpleNamespace(stdout=str(int(memory_gib * 1024**3)))
        assert command[:2] == ['docker', 'ps']
        assert any('project.working_dir=' in value for value in command)
        return SimpleNamespace(stdout=projects)
    return run


def test_undersized_vm_with_existing_repository_stack_fails_before_startup():
    module = smoke_module()
    with pytest.raises(RuntimeError, match='Docker memory'):
        module.ensure_stack_capacity(run=docker_snapshot(3.69, 'cognitive-traffic\n'))


def test_small_vm_without_another_repository_stack_can_run_isolated_demo():
    smoke_module().ensure_stack_capacity(run=docker_snapshot(3.69, ''))


def test_larger_vm_can_run_concurrent_repository_stacks():
    smoke_module().ensure_stack_capacity(run=docker_snapshot(7, 'cognitive-traffic\n'))
