"""Configured Markdown discovery and explicit path selection."""

import os
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from mdrepo.config import ApplicationConfig
from mdrepo.files import FileDiscoveryError, collect_project_markdown, select_requested_markdown
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


def test_project_discovery_handles_spaces_newlines_and_long_names(
    repository: RepositoryBuilder,
) -> None:
    relative_paths = (
        "docs/with spaces.md",
        f"docs/{'x' * 160}.md",
    )
    for relative in relative_paths:
        repository.markdown(relative, "# Document\n")
    config = ApplicationConfig.model_validate({"include": ["**/*.md"]})

    discovered = {
        path.relative_to(repository.root).as_posix()
        for path in collect_project_markdown(root=repository.root, config=config)
    }

    assert discovered == set(relative_paths)


@pytest.mark.skipif(os.name == "nt", reason="Windows filenames cannot contain control characters")
def test_project_discovery_handles_newline_names(repository: RepositoryBuilder) -> None:
    relative = "docs/with\nnewline.md"
    repository.markdown(relative, "# Document\n")
    config = ApplicationConfig.model_validate({"include": ["**/*.md"]})

    discovered = collect_project_markdown(root=repository.root, config=config)

    assert [path.relative_to(repository.root).as_posix() for path in discovered] == [relative]


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


def test_project_discovery_reports_filesystem_inspection_errors(
    monkeypatch: pytest.MonkeyPatch,
    repository: RepositoryBuilder,
) -> None:
    candidate = repository.markdown("docs/guide.md", "# Guide\n")
    original_stat = Path.stat

    def failing_stat(path: Path, *args: object, **kwargs: object) -> object:
        if path == candidate:
            raise OSError("path is too long")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", failing_stat)
    config = ApplicationConfig.model_validate({})

    with pytest.raises(FileDiscoveryError, match="unable to inspect repository"):
        collect_project_markdown(root=repository.root, config=config)


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
