"""Tests for kevin.subprocess_utils — heartbeat and CI progress lines."""

import os
from pathlib import Path

import pytest

from kevin.subprocess_utils import run_with_heartbeat


@pytest.fixture
def progress_every_1s(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEVIN_SUBPROCESS_PROGRESS_INTERVAL", "1")


@pytest.fixture
def no_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEVIN_SUBPROCESS_PROGRESS_INTERVAL", "0")


def test_progress_logs_to_stderr_while_child_silent(capsys: pytest.CaptureFixture[str], progress_every_1s: None) -> None:
    r = run_with_heartbeat(["sleep", "3"], cwd=Path("."), timeout=15)
    assert r.success
    err = capsys.readouterr().err
    assert "[kevin] subprocess still running" in err
    assert "silence limit" in err


def test_no_progress_lines_when_interval_zero(capsys: pytest.CaptureFixture[str], no_progress: None) -> None:
    r = run_with_heartbeat(["echo", "ok"], cwd=Path("."), timeout=5)
    assert r.success
    err = capsys.readouterr().err
    assert "[kevin] subprocess still running" not in err
