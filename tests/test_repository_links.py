"""Same-repository provider URL detection."""

from pathlib import Path

import pytest

from mdrepo.cli import main
from mdrepo.repository import (
    RepositoryIdentity,
    normalize_repository_url,
    parse_same_repository_url,
)


def test_git_remote_normalization() -> None:
    assert normalize_repository_url("git@github.com:acme/demo.git") == (
        "https://github.com/acme/demo"
    )
    assert normalize_repository_url("ssh://git@gitlab.example/acme/demo.git") == (
        "https://gitlab.example/acme/demo"
    )
####




def test_invalid_repository_port_is_a_cli_configuration_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.mdrepo.repository]
url = "https://github.com:not-a-port/acme/demo"
discover-from-git = false
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    assert main(["check", "."]) == 2
    assert "invalid repository URL" in capsys.readouterr().err
####




def test_github_and_gitlab_blob_routes() -> None:
    github = RepositoryIdentity(
        web_url="https://github.com/acme/demo",
        provider="github",
        host="github.com",
        base_path="/acme/demo",
        refs=("feature/docs", "main"),
        source="test",
    )
    target = parse_same_repository_url(
        target="https://github.com/acme/demo/blob/feature/docs/guide.md#setup",
        identity=github,
    )
    assert target is not None
    assert target.ref == "feature/docs"
    assert target.repository_path.as_posix() == "guide.md"

    gitlab = RepositoryIdentity(
        web_url="https://gitlab.example/group/subgroup/demo",
        provider="gitlab",
        host="gitlab.example",
        base_path="/group/subgroup/demo",
        refs=("main",),
        source="test",
    )
    target = parse_same_repository_url(
        target="https://gitlab.example/group/subgroup/demo/-/blob/main/docs/guide.md",
        identity=gitlab,
    )
    assert target is not None
    assert target.repository_path.as_posix() == "docs/guide.md"
####




def test_bitbucket_src_route() -> None:
    identity = RepositoryIdentity(
        web_url="https://bitbucket.org/acme/demo",
        provider="bitbucket",
        host="bitbucket.org",
        base_path="/acme/demo",
        refs=("main",),
        source="test",
    )

    target = parse_same_repository_url(
        target="https://bitbucket.org/acme/demo/src/main/docs/guide.md",
        identity=identity,
    )

    assert target is not None
    assert target.ref == "main"
    assert target.repository_path.as_posix() == "docs/guide.md"
####




def test_repository_port_is_part_of_same_repository_identity() -> None:
    identity = RepositoryIdentity(
        web_url="https://github.com:8443/acme/demo",
        provider="github",
        host="github.com",
        base_path="/acme/demo",
        refs=("main",),
        source="test",
        port=8443,
    )

    assert (
        parse_same_repository_url(
            target="https://github.com/acme/demo/blob/main/docs/guide.md",
            identity=identity,
        )
        is None
    )
    assert (
        parse_same_repository_url(
            target="https://github.com:8443/acme/demo/blob/main/docs/guide.md",
            identity=identity,
        )
        is not None
    )
####




def test_mutable_same_repository_link_is_fixed_but_commit_and_line_links_remain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.mdrepo.repository]
url = "https://github.com/acme/demo"
discover-from-git = false
relative-refs = ["main"]
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        """[Mutable](https://github.com/acme/demo/blob/main/docs/guide.md#setup)
[Commit](https://github.com/acme/demo/blob/0123456789abcdef/docs/guide.md)
[Line](https://github.com/acme/demo/blob/main/docs/guide.md#L1)
""",
        encoding="utf-8",
    )

    assert main(["fix", "."]) == 0
    capsys.readouterr()
    updated = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "[Mutable](docs/guide.md#setup)" in updated
    assert "/blob/0123456789abcdef/" in updated
    assert "/blob/main/docs/guide.md#L1" in updated
####


