"""Source-aware Markdown destination parsing."""

from pathlib import Path

from mdrepo.markdown import MarkdownParser
from mdrepo.models import LinkKind, LinkSourceKind

def test_direct_links_reference_definitions_and_code_are_distinguished(tmp_path: Path) -> None:
    text = """# Demo

[Direct](docs/a.md) and [Reference][guide]

`[Code](docs/nope.md)`

```md
[Fenced](docs/nope.md)
```

[guide]: docs/b.md "Guide"
"""
    path = tmp_path / "README.md"
    path.write_bytes(text.encode())

    document = MarkdownParser().parse(path=path, root=tmp_path, text=text)

    assert [link.target for link in document.links] == ["docs/a.md", "docs/b.md"]
    assert document.links[0].source_kind is LinkSourceKind.DIRECT
    assert document.links[0].span is not None
    assert document.links[1].source_kind is LinkSourceKind.REFERENCE_USE
    assert document.links[1].span is None
    assert len(document.reference_definitions) == 1
    definition = document.reference_definitions[0]
    assert definition.target == "docs/b.md"
    assert definition.raw_target == "docs/b.md"
    assert definition.span is not None
    assert text[definition.span.start: definition.span.end] == "docs/b.md"

def test_repeated_destinations_receive_distinct_source_spans(tmp_path: Path) -> None:
    text = "[A](docs/a.md) and [B](docs/a.md)\n"
    path = tmp_path / "README.md"
    document = MarkdownParser().parse(path=path, root=tmp_path, text=text)

    spans = [link.span for link in document.links]
    assert all(span is not None for span in spans)
    assert spans[0] != spans[1]
    assert [span.column for span in spans if span is not None] == [5, 24]

def test_link_span_ignores_same_target_in_prose_parentheses(tmp_path: Path) -> None:
    text = "Mention (docs\\guide.md), then [Guide](docs\\guide.md)\n"
    path = tmp_path / "README.md"
    document = MarkdownParser().parse(path=path, root=tmp_path, text=text)

    occurrence = document.links[0]
    assert occurrence.span is not None
    assert text[occurrence.span.start: occurrence.span.end] == "docs\\guide.md"
    assert occurrence.span.start == text.rindex("docs\\guide.md")

def test_crlf_offsets_are_preserved(tmp_path: Path) -> None:
    text = "# Demo\r\n\r\n[Guide](docs\\guide.md)\r\n"
    path = tmp_path / "README.md"
    document = MarkdownParser().parse(path=path, root=tmp_path, text=text)

    occurrence = document.links[0]
    assert occurrence.span is not None
    assert text[occurrence.span.start: occurrence.span.end] == "docs\\guide.md"
    assert occurrence.line == 3
    assert occurrence.column == 9

def test_images_and_autolinks_are_recorded(tmp_path: Path) -> None:
    text = "![Logo](assets/logo.png)\n\n<https://example.com/docs>\n"
    path = tmp_path / "README.md"
    path.write_bytes(text.encode())

    document = MarkdownParser().parse(path=path, root=tmp_path, text=text)

    assert [(link.kind, link.target) for link in document.links] == [
        (LinkKind.IMAGE, "assets/logo.png"),
        (LinkKind.LINK, "https://example.com/docs"),
    ]
    assert document.links[1].source_kind is LinkSourceKind.AUTOLINK

def test_nested_and_angle_destinations_preserve_decoded_targets(tmp_path: Path) -> None:
    text = '[Nested](docs/guide_(v2).md "Guide")\n[Angle](<docs/guide two.md>)\n'
    path = tmp_path / "README.md"

    document = MarkdownParser().parse(path=path, root=tmp_path, text=text)

    assert [link.target for link in document.links] == [
        "docs/guide_(v2).md",
        "docs/guide%20two.md",
    ]
    assert [link.raw_target for link in document.links] == [
        "docs/guide_(v2).md",
        "docs/guide two.md",
    ]

def test_reference_labels_are_case_insensitive_and_definitions_are_checked_once(
        tmp_path: Path,
) -> None:
    text = "[One][GUIDE] and [Two][guide]\n\n[guide]: docs/Guide.md\n"
    path = tmp_path / "README.md"

    document = MarkdownParser().parse(path=path, root=tmp_path, text=text)

    assert len(document.links) == 2
    assert all(link.source_kind is LinkSourceKind.REFERENCE_USE for link in document.links)
    assert [link.target for link in document.links] == ["docs/Guide.md", "docs/Guide.md"]
    assert len(document.reference_definitions) == 1
    assert [link.target for link in document.policy_occurrences] == ["docs/Guide.md"]

def test_non_markdown_angle_links_and_html_are_not_policy_destinations(tmp_path: Path) -> None:
    text = '<mailto:team@example.com> <https://example.com>\n<a href="docs/nope.md">HTML</a>\n'
    path = tmp_path / "README.md"

    document = MarkdownParser().parse(path=path, root=tmp_path, text=text)

    assert [link.target for link in document.links] == [
        "mailto:team@example.com",
        "https://example.com",
    ]

def test_reference_definition_angle_destination_and_titles_keep_editable_span(
        tmp_path: Path,
) -> None:
    text = '[Guide][docs]\n\n[docs]: <docs/guide two.md> "Guide title"\n'
    path = tmp_path / "README.md"

    document = MarkdownParser().parse(path=path, root=tmp_path, text=text)

    definition = document.reference_definitions[0]
    assert definition.target == "docs/guide%20two.md"
    assert definition.raw_target == "docs/guide two.md"
    assert definition.span is not None
    assert text[definition.span.start: definition.span.end] == "docs/guide two.md"

def test_code_spans_fences_and_malformed_destinations_are_not_recorded(tmp_path: Path) -> None:
    text = """`[Code](docs/code.md)`

```markdown
[Fence](docs/fence.md)
```

[Broken](docs/unfinished
"""
    path = tmp_path / "README.md"

    document = MarkdownParser().parse(path=path, root=tmp_path, text=text)

    assert document.links == ()
