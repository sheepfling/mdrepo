"""Provider-neutral release metadata and artifact command coverage."""

import subprocess
import tomllib
from pathlib import Path

import pytest

from scripts import release


def test_project_version_is_scm_dynamic() -> None:
    with (release.ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]

    assert project["dynamic"] == ["version"]
    assert "version" not in project


def test_release_version_and_tag_validation() -> None:
    version = release.project_version()
    assert version
    release.verify_tag(f"v{version}")
    release.verify_tag(version)

    with pytest.raises(release.ReleaseError, match="does not match"):
        release.verify_tag("v9.9.9")


def test_release_build_runs_build_and_twine_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = release.project_version()
    stale = tmp_path / "mdrepo-0.1.0-py3-none-any.whl"
    stale.write_bytes(b"stale wheel")
    unrelated = tmp_path / "release-notes.txt"
    unrelated.write_text("keep", encoding="utf-8")
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if "build" in command:
            (tmp_path / f"mdrepo-{version}.tar.gz").write_bytes(b"sdist")
            (tmp_path / f"mdrepo-{version}-py3-none-any.whl").write_bytes(b"wheel")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(release.subprocess, "run", fake_run)

    distributions = release.build_release(output=tmp_path, tag=f"v{version}")

    assert [path.suffix for path in distributions] == [".whl", ".gz"]
    assert not stale.exists()
    assert unrelated.exists()
    assert all("0.1.0" not in argument for argument in commands[1])
    assert commands[0][1:5] == ["-m", "build", "--sdist", "--wheel"]
    assert commands[1][1:4] == ["-m", "twine", "check"]
