"""Contracts for the local CI runner and packaging validation script."""

import subprocess
from collections.abc import Sequence
from typing import cast

import pytest

from scripts import check_build, ci
from tests.constants import COVERAGE_ARGUMENT, MODULE_COMMAND, PYTEST_COMMAND


def test_ci_command_sets_keep_read_only_and_fix_modes_distinct() -> None:
    readonly = ci.ci_commands("python", fix=False)
    fixing = ci.ci_commands("python", fix=True)

    assert (
        "python",
        *PYTEST_COMMAND,
        COVERAGE_ARGUMENT,
        "--cov-report=term-missing",
    ) in readonly
    assert all("--cov-fail-under" not in command for command in readonly)
    assert ("python", *MODULE_COMMAND, "fix", ".") not in readonly
    assert ("python", "-m", "scripts.check_format") in readonly
    assert ("python", "-m", "ruff", "check", "src", "scripts", "tests") in readonly
    assert ("python", *MODULE_COMMAND, "fix", ".") in fixing
    assert ("python", "-m", "scripts.check_rumdl", "--fix") in fixing
    assert len(fixing) > len(readonly)


def test_ci_runner_maps_unstartable_commands_to_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_os_error(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("missing executable")

    monkeypatch.setattr(ci.subprocess, "run", raise_os_error)

    assert ci.run_command(("missing-python", "-m", "pytest")) == 1


def test_ci_runner_executes_every_command_until_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands = (("python", "first"), ("python", "second"), ("python", "third"))
    executed: list[tuple[str, ...]] = []

    def fake_commands(*, fix: bool = False) -> tuple[tuple[str, ...], ...]:
        _ = fix
        return commands

    def fake_run_command(command: Sequence[str]) -> int:
        executed.append(tuple(command))
        return 0

    monkeypatch.setattr(ci, "ci_commands", fake_commands)
    monkeypatch.setattr(ci, "run_command", fake_run_command)

    assert ci.main(()) == 0
    assert executed == list(commands)


def test_build_check_runs_sdist_wheel_then_twine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []
    environments: list[dict[str, str]] = []

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        environment = kwargs.get("env")
        if environment is not None:
            assert isinstance(environment, dict)
            environments.append(cast(dict[str, str], environment))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(check_build.subprocess, "run", fake_run)

    assert check_build.main() == 0
    assert commands[0][1:4] == ["-m", "build", "--sdist"]
    assert "--wheel" in commands[0]
    assert commands[1][1:4] == ["-m", "twine", "check"]
    assert environments[0][check_build.SCM_VERSION_ENV] == check_build.package_version(
        check_build.PACKAGE_NAME
    )
