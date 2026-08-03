"""Configured Markdown discovery and explicit path selection."""

import os
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from mdrepo.cli import main
from mdrepo.config import ApplicationConfig
from mdrepo.files import (
    FileDiscoveryError,
    TargetDurabilityPolicy,
    collect_project_markdown,
    select_requested_markdown,
)
from tests.support import RepositoryBuilder


def test_project_discovery_applies_include_exclude_and_ignores_symlinks(
    repository: RepositoryBuilder,
) -> None:
    repository.markdown("README.md", "# Root\n")
    repository.markdown("docs/guide.md", "# Guide\n")
    repository.markdown("site/generated.md", "# Generated\n")
    repository.write_text("notes.txt", "not Markdown\n")

    config = ApplicationConfig.model_validate(
        {"exclude": ["site/**"], "include": ["*.md", "**/*.md"]}
    )

    assert [
        path.relative_to(repository.root).as_posix()
        for path in collect_project_markdown(root=repository.root, config=config)
    ] == ["README.md", "docs/guide.md"]


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="named pipes are not supported on this OS")
def test_project_discovery_ignores_non_regular_files(repository: RepositoryBuilder) -> None:
    """A matching FIFO must not enter the set of files later read by the engine."""

    fifo = repository.root / "pipe.py"
    mkfifo = cast(Callable[[str], None] | None, getattr(os, "mkfifo", None))
    if mkfifo is None:
        pytest.skip("named pipes are not supported on this OS")
    mkfifo(str(fifo))
    config = ApplicationConfig.model_validate({"include": ["*.py"]})

    assert collect_project_markdown(root=repository.root, config=config) == ()


def test_project_discovery_requires_regular_file(
    monkeypatch: pytest.MonkeyPatch,
    repository: RepositoryBuilder,
) -> None:
    """A matching candidate reported as non-regular must be ignored."""

    candidate = repository.write_text("pipe.py", "would block if opened\n")
    original_is_file = Path.is_file

    def pretend_non_regular(path: Path) -> bool:
        if path == candidate:
            return False
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", pretend_non_regular)
    config = ApplicationConfig.model_validate({"include": ["*.py"]})

    assert collect_project_markdown(root=repository.root, config=config) == ()


def test_requested_selection_deduplicates_files_and_rejects_invalid_inputs(
    repository: RepositoryBuilder,
) -> None:
    repository.markdown("README.md", "# Root\n")
    repository.markdown("docs/guide.md", "# Guide\n")
    repository.markdown("docs/other.md", "# Other\n")
    config = ApplicationConfig.model_validate({})
    project = collect_project_markdown(root=repository.root, config=config)

    selected = select_requested_markdown(
        root=repository.root,
        requested_paths=["README.md", "docs", "README.md"],
        project_paths=project,
    )
    assert [path.relative_to(repository.root).as_posix() for path in selected] == [
        "README.md",
        "docs/guide.md",
        "docs/other.md",
    ]

    with pytest.raises(FileDiscoveryError, match="does not exist"):
        select_requested_markdown(
            root=repository.root,
            requested_paths=["missing.md"],
            project_paths=project,
        )

    outside = repository.root.parent / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    with pytest.raises(FileDiscoveryError, match="outside the project root"):
        select_requested_markdown(
            root=repository.root,
            requested_paths=[str(outside)],
            project_paths=project,
        )


def test_requested_non_markdown_file_is_rejected_by_include_policy(
    repository: RepositoryBuilder,
) -> None:
    repository.markdown("README.md", "# Root\n")
    repository.write_text("notes.txt", "notes\n")
    config = ApplicationConfig.model_validate({})
    project = collect_project_markdown(root=repository.root, config=config)

    with pytest.raises(FileDiscoveryError, match="not selected"):
        select_requested_markdown(
            root=repository.root,
            requested_paths=["notes.txt"],
            project_paths=project,
        )


def test_requested_symlinked_markdown_file_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    repository: RepositoryBuilder,
) -> None:
    repository.markdown("README.md", "# Root\n")
    link = repository.root / "linked.md"
    try:
        link.symlink_to(repository.root / "README.md")
    except OSError:
        original_is_symlink = Path.is_symlink

        def simulated_is_symlink(path: Path) -> bool:
            return path == link or original_is_symlink(path)

        monkeypatch.setattr(Path, "is_symlink", simulated_is_symlink)

    config = ApplicationConfig.model_validate({})
    project = collect_project_markdown(root=repository.root, config=config)

    with pytest.raises(FileDiscoveryError, match="must not be a symlink"):
        select_requested_markdown(
            root=repository.root,
            requested_paths=["linked.md"],
            project_paths=project,
        )


@pytest.mark.parametrize(
    ("pattern", "relative"),
    [
        ("secret.md", "secret.md"),
        ("artifacts/", "artifacts/release.txt"),
        ("*.tmp", "logs/cache.tmp"),
        ("**/generated/*.md", "docs/archive/generated/guide.md"),
        ("docs/**/draft.md", "docs/archive/2026/draft.md"),
    ],
)
def test_durability_policy_matches_gitignore_pattern_forms(
    repository: RepositoryBuilder,
    pattern: str,
    relative: str,
) -> None:
    repository.write_text(".gitignore", f"{pattern}\n")
    target = repository.write_text(relative, "target\n")
    policy = TargetDurabilityPolicy.from_repository(
        root=repository.root,
        exclude_patterns=(),
    )

    assert policy.classify(target).gitignored is True


def test_durability_policy_honors_gitignore_and_mdrepo_overrides(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(
        ".gitignore",
        "*.md\n!README.md\n!docs/keep.md\n",
    )
    readme = repository.write_text("README.md", "# Root\n")
    keep = repository.write_text("docs/keep.md", "# Keep\n")
    drop = repository.write_text("docs/drop.md", "# Drop\n")
    artifact = repository.write_text("artifacts/keep.txt", "artifact\n")
    policy = TargetDurabilityPolicy.from_repository(
        root=repository.root,
        exclude_patterns=("artifacts/**", "!artifacts/keep.txt"),
    )

    assert policy.classify(readme).excluded is False
    assert policy.classify(keep).excluded is False
    assert policy.classify(drop).gitignored is True
    assert policy.classify(artifact).mdrepo_excluded is False


def test_durability_policy_does_not_require_git_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    (tmp_path / ".gitignore").write_text("scratch/\n", encoding="utf-8")
    (tmp_path / "scratch").mkdir()
    (tmp_path / "scratch" / "guide.md").write_text("# Scratch\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("[Scratch](scratch/guide.md)\n", encoding="utf-8")

    assert main(["check", "."]) == 1
    assert "MDR006" in capsys.readouterr().out


def test_unreadable_gitignore_is_a_reported_cli_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_bytes(b"\xff\xfe")
    (tmp_path / "target.txt").write_text("target\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("[Target](target.txt)\n", encoding="utf-8")

    assert main(["check", "."]) == 2
    assert "unable to read repository .gitignore" in capsys.readouterr().err
