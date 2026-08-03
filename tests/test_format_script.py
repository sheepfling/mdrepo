"""Read-only formatting compatibility checks."""

import subprocess

import pytest

from scripts import check_format


def test_format_check_does_not_rewrite_before_checking(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(check_format.subprocess, "run", fake_run)

    assert check_format.main() == 0
    assert len(commands) == 1
    assert "--check" in commands[0]
