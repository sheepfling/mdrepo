"""Provider-neutral release metadata and artifact command coverage."""

import subprocess
from pathlib import Path

import pytest

from scripts import release


def test_release_version_and_tag_validation() -> None:
    assert release.project_version() == "0.2.1"
    release.verify_tag("v0.2.1")
    release.verify_tag("0.2.1")

    with pytest.raises(release.ReleaseError, match="does not match"):
        release.verify_tag("v9.9.9")


def test_release_build_runs_build_and_twine_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if "build" in command:
            (tmp_path / "markdown_repo_policy-0.2.1.tar.gz").write_bytes(b"sdist")
            (tmp_path / "markdown_repo_policy-0.2.1-py3-none-any.whl").write_bytes(b"wheel")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(release.subprocess, "run", fake_run)

    distributions = release.build_release(output=tmp_path, tag="v0.2.1")

    assert [path.suffix for path in distributions] == [".whl", ".gz"]
    assert commands[0][1:5] == ["-m", "build", "--sdist", "--wheel"]
    assert commands[1][1:4] == ["-m", "twine", "check"]
