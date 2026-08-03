"""Configured Markdown discovery and explicit path selection."""

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
