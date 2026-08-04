"""Tests for PathPolicy kernel."""

from __future__ import annotations

import pytest

from ai_agent.domain.path_policy import PathPolicy


def test_allows_src_and_tests() -> None:
    policy = PathPolicy()
    assert policy.is_allowed("src/ai_agent/tools/foo.py")
    assert policy.is_allowed("tests/domain/test_x.py")
    assert policy.is_allowed("config/agents/engineer.yaml")
    assert policy.is_allowed("README.md")


def test_denies_kernel_and_secrets() -> None:
    policy = PathPolicy()
    assert not policy.is_allowed("src/ai_agent/domain/path_policy.py")
    assert not policy.is_allowed(".env")
    assert not policy.is_allowed(".git/config")
    assert not policy.is_allowed(".ai_agent/evolve/STOP")


def test_assert_writable_raises() -> None:
    policy = PathPolicy()
    with pytest.raises(PermissionError):
        policy.assert_writable("src/ai_agent/domain/path_policy.py")
    assert policy.assert_writable("src/ok.py") == "src/ok.py"


def test_rejects_path_traversal() -> None:
    policy = PathPolicy()
    with pytest.raises(ValueError):
        policy.normalize("../etc/passwd")
