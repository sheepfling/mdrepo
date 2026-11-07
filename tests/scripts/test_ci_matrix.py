"""Contracts for the local multi-version CI runner."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import ci_matrix


def test_supported_versions_cover_metadata_boundaries() -> None:
    assert ci_matrix.SUPPORTED_VERSIONS == ("3.10", "3.11", "3.12", "3.13", "3.14", "3.15")


def test_interpreter_prefers_the_running_supported_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ci_matrix.sys, "version_info", SimpleNamespace(major=3, minor=12))
    monkeypatch.setattr(ci_matrix.sys, "executable", "/usr/bin/python3.12")

    def no_interpreter(_name: str) -> str | None:
        return None

    monkeypatch.setattr(ci_matrix.shutil, "which", no_interpreter)

    assert ci_matrix.find_interpreter("3.12") == ("/usr/bin/python3.12",)


def test_environment_python_uses_current_platform_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ci_matrix, "ROOT", Path("/repo"))
    monkeypatch.setattr(ci_matrix.sys, "platform", "win32")

    assert ci_matrix.environment_python("3.10") == Path("/repo/.venv-ci-3.10/Scripts/python.exe")
