"""Contracts for the local CI runner and packaging validation script."""

import subprocess

import pytest

from scripts import check_build, ci


def test_ci_command_sets_keep_read_only_and_fix_modes_distinct() -> None:
    readonly = ci.ci_commands("python", fix=False)
    fixing = ci.ci_commands("python", fix=True)

    assert ("python", "-m", "pytest", "--cov=mdrepo", "--cov-report=term-missing") in readonly
    assert all("--cov-fail-under" not in command for command in readonly)
    assert ("python", "-m", "mdrepo", "fix", ".") not in readonly
    assert ("python", "scripts/check_format.py") in readonly
    assert ("python", "-m", "ruff", "check", "src", "scripts", "tests") in readonly
    assert ("python", "-m", "mdrepo", "fix", ".") in fixing
    assert len(fixing) > len(readonly)


def test_ci_runner_maps_unstartable_commands_to_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_os_error(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("missing executable")

    monkeypatch.setattr(ci.subprocess, "run", raise_os_error)

    assert ci.run_command(("missing-python", "-m", "pytest")) == 1


def test_build_check_runs_sdist_wheel_then_twine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(check_build.subprocess, "run", fake_run)

    assert check_build.main() == 0
    assert commands[0][1:4] == ["-m", "build", "--sdist"]
    assert "--wheel" in commands[0]
    assert commands[1][1:4] == ["-m", "twine", "check"]
