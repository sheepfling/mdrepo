"""Filesystem target classification and document resolution coverage."""

from pathlib import Path, PurePosixPath

import pytest

from mdrepo.config import LinkConfig, OrphanConfig
from mdrepo.markdown import MarkdownParser
from mdrepo.models import Document, LinkKind, LinkOccurrence, LinkSourceKind
from mdrepo.resolution import (
    canonicalize_case,
    make_relative_target,
    make_repository_target,
    resolve_graph_document,
    resolve_local_target,
)

def _document(root: Path, relative: str = "README.md") -> Document:
    path = root / relative
    return Document(
        path=path,
        relative_path=Path(relative),
        text="",
        links=(),
        reference_definitions=(),
    )

def _occurrence(target: str) -> LinkOccurrence:
    return LinkOccurrence(
        target=target,
        raw_target=target,
        kind=LinkKind.LINK,
        source_kind=LinkSourceKind.DIRECT,
        line=1,
        column=1,
        span=None,
    )

@pytest.mark.parametrize(
    ("target", "attribute"),
    [
        ("C:/Users/example/docs/guide.md", "windows_absolute"),
        ("\\\\server\\share\\guide.md", "windows_absolute"),
        ("/docs/guide.md", "root_relative"),
        ("//example.com/docs/guide.md", "protocol_relative"),
        ("file:///Users/example/docs/guide.md", "file_uri"),
        ("~/docs/guide.md", "home_relative"),
    ],
)
def test_local_target_classifies_machine_and_root_absolute_forms(
        tmp_path: Path,
        target: str,
        attribute: str,
) -> None:
    resolution = resolve_local_target(
        root=tmp_path,
        document=_document(tmp_path),
        occurrence=_occurrence(target),
        config=LinkConfig(),
    )

    assert resolution is not None
    assert getattr(resolution, attribute) is True
    assert resolution.absolute is True
    if attribute == "root_relative":
        assert resolution.candidate_path == tmp_path / "docs" / "guide.md"
    else:
        assert resolution.candidate_path is None

@pytest.mark.parametrize("target", ("", "#section", "?query", "https://example.com/docs"))
def test_non_local_or_fragment_targets_are_not_resolved(tmp_path: Path, target: str) -> None:
    assert (
            resolve_local_target(
                root=tmp_path,
                document=_document(tmp_path),
                occurrence=_occurrence(target),
                config=LinkConfig(),
            )
            is None
    )

def test_local_target_resolves_case_and_repository_escape(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "Guide.md").write_text("# Guide\n", encoding="utf-8")
    document = _document(tmp_path, "docs/README.md")

    mismatch = resolve_local_target(
        root=tmp_path,
        document=document,
        occurrence=_occurrence("guide.md"),
        config=LinkConfig(),
    )
    assert mismatch is not None
    assert mismatch.exists is True
    assert mismatch.case_mismatch is True
    assert mismatch.canonical_path == tmp_path / "docs" / "Guide.md"

    escaped = resolve_local_target(
        root=tmp_path,
        document=document,
        occurrence=_occurrence("../../outside.md"),
        config=LinkConfig(),
    )
    assert escaped is not None
    assert escaped.outside_root is True
    assert escaped.suggested_target is None

def test_case_canonicalization_distinguishes_exact_missing_and_outside_paths(
        tmp_path: Path,
) -> None:
    (tmp_path / "Docs").mkdir()
    (tmp_path / "Docs" / "Guide.md").write_text("# Guide\n", encoding="utf-8")

    canonical, exists, mismatch = canonicalize_case(
        root=tmp_path,
        candidate=tmp_path / "docs" / "guide.md",
    )
    assert canonical == tmp_path / "Docs" / "Guide.md"
    assert exists is True
    assert mismatch is True

    missing, exists, mismatch = canonicalize_case(
        root=tmp_path,
        candidate=tmp_path / "missing.md",
    )
    assert missing is None
    assert exists is False
    assert mismatch is False

    outside, exists, mismatch = canonicalize_case(
        root=tmp_path,
        candidate=tmp_path.parent / "outside.md",
    )
    assert outside is None
    assert exists is False
    assert mismatch is False

def test_target_rendering_quotes_paths_and_preserves_query_fragments(tmp_path: Path) -> None:
    source = tmp_path / "docs" / "README.md"
    target = tmp_path / "docs" / "guide with space.md"
    assert (
            make_relative_target(
                source=source,
                target=target,
                query="raw=1",
                fragment="setup",
            )
            == "guide%20with%20space.md?raw=1#setup"
    )

    target_path, replacement = make_repository_target(
        root=tmp_path,
        source=source,
        repository_path=PurePosixPath("guide.md"),
        fragment="intro",
    )
    assert target_path == tmp_path / "guide.md"
    assert replacement == "../guide.md#intro"

def test_extensionless_graph_resolution_uses_configured_markdown_extensions(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    guide = tmp_path / "docs" / "guide.markdown"
    guide.write_text("# Guide\n", encoding="utf-8")
    source = tmp_path / "README.md"
    source.write_text("[Guide](docs/guide)\n", encoding="utf-8")
    document = MarkdownParser().parse(path=source, root=tmp_path, text=source.read_text())
    resolution = resolve_local_target(
        root=tmp_path,
        document=document,
        occurrence=document.links[0],
        config=LinkConfig(),
    )
    assert resolution is not None
    documents = {guide.resolve(): _document(tmp_path, "docs/guide.markdown")}

    assert (
            resolve_graph_document(
                root=tmp_path,
                resolution=resolution,
                documents=documents,
                config=OrphanConfig(markdown_extensions=[".md", ".markdown"]),
            )
            == guide.resolve()
    )
