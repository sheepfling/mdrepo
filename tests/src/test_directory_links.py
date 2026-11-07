"""Directory slash fixes preserve Markdown syntax and repository graph semantics."""

from pathlib import Path

import pytest

from mdrepo.cli import main


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ('[docs/](docs/ "title/")\n', '[docs/](docs "title/")\n'),
        ('[Docs](<docs/> "title")\n', '[Docs](<docs> "title")\n'),
        ("[Docs](docs/?q=a%20b&x=/#part/)\n", "[Docs](docs?q=a%20b&x=/#part/)\n"),
        ("[Docs](./docs//#)\n", "[Docs](./docs#)\n"),
        ("[Docs](docs/?)\n", "[Docs](docs?)\n"),
        ("[Docs](d%6fcs/)\n", "[Docs](d%6fcs)\n"),
        ("[Docs](docs/?q=%3F%23&amp;x=1#part)\n", "[Docs](docs?q=%3F%23&amp;x=1#part)\n"),
        ("[Docs](docs%2F)\n", "[Docs](docs)\n"),
        ("[Docs](docs&percnt;2F)\n", "[Docs](docs)\n"),
        ("[Docs](docs%2&#70;)\n", "[Docs](docs)\n"),
        ("[Docs](docs&#37;&#50;&#102;?q=%23)\n", "[Docs](docs?q=%23)\n"),
        ("[Docs](docs&percnt;2F/%2&#70;#part)\n", "[Docs](docs#part)\n"),
        ("[Docs](d&#111;cs/)\n", "[Docs](d&#111;cs)\n"),
        ("[Docs](docs&#47;)\n", "[Docs](docs)\n"),
        ("[Docs](docs&sol;)\n", "[Docs](docs)\n"),
        ("[Docs](docs/&#63;q=1&#35;part)\n", "[Docs](docs&#63;q=1&#35;part)\n"),
        ("[Docs](docs/\\?q=1)\n", "[Docs](docs\\?q=1)\n"),
        ("[Self](./)\n", "[Self](.)\n"),
        ('![Docs](docs/ "caption")\n', '![Docs](docs "caption")\n'),
        (
            '[One][ref] and [Two][ref]\n\n[ref]: <docs/?q=/#part/> "title/"\n',
            '[One][ref] and [Two][ref]\n\n[ref]: <docs?q=/#part/> "title/"\n',
        ),
        (
            "docs/ `[Docs](docs/)`\n\n```md\n[Docs](docs/)\n```\n\n[Docs](docs/)\n",
            "docs/ `[Docs](docs/)`\n\n```md\n[Docs](docs/)\n```\n\n[Docs](docs)\n",
        ),
    ],
)
def test_directory_fix_only_changes_parsed_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    original: str,
    expected: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    source = tmp_path / "README.md"
    source.write_text(original, encoding="utf-8")

    assert main(["check", "."]) == 1
    assert "MDR007" in capsys.readouterr().out
    assert main(["fix", ".", "--dry-run"]) == 1
    assert source.read_text(encoding="utf-8") == original
    assert main(["fix", "."]) == 0
    assert source.read_text(encoding="utf-8") == expected
    assert main(["fix", "."]) == 0
    assert source.read_text(encoding="utf-8") == expected


@pytest.mark.parametrize(
    "target",
    [
        "https://example.com/docs/",
        "//example.com/docs/",
        "/docs/",
        "missing/",
        "file.md/",
        "file:///tmp/docs/",
        "C:/temp/docs/",
        "~/docs/",
        "../",
        "#part/",
        "?query=/",
        "docs?q=/",
        "docs#part/",
    ],
)
def test_directory_rule_leaves_other_destinations_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "file.md").write_text("# File\n", encoding="utf-8")
    source = tmp_path / "README.md"
    original = f"[Target]({target})\n"
    source.write_text(original, encoding="utf-8")

    assert main(["fix", ".", "--select", "MDR007"]) == 0
    assert source.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("target", ["docs/guide/", "docs\\guide/", "docs\\guide%5C"])
def test_directory_case_and_backslash_fixes_share_one_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Docs" / "Guide").mkdir(parents=True)
    source = tmp_path / "README.md"
    source.write_text(f'[Guide](<{target}?#> "title")\n', encoding="utf-8")

    assert main(["fix", "."]) == 0
    assert source.read_text(encoding="utf-8") == '[Guide](<Docs/Guide?#> "title")\n'
    assert main(["check", "."]) == 0


@pytest.mark.parametrize("index", ["README.md", "index.md"])
def test_directory_index_graph_is_unchanged_by_fix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    index: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / index).write_text("# Guide\n", encoding="utf-8")
    source = tmp_path / "README.md"
    source.write_text("[Docs](docs/)\n", encoding="utf-8")
    args = [".", "--set", "orphans.enabled=true"]

    assert main(["check", *args, "--ignore", "MDR007"]) == 0
    assert main(["fix", *args]) == 0
    assert source.read_text(encoding="utf-8") == "[Docs](docs)\n"
    assert main(["check", *args]) == 0


def test_directory_symlink_outside_repository_is_not_fixed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    try:
        (tmp_path / "escape").symlink_to(tmp_path.parent, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlinks are unavailable: {error}")
    source = tmp_path / "README.md"
    source.write_text("[Escape](escape/)\n", encoding="utf-8")

    assert main(["fix", "README.md", "--select", "MDR007"]) == 0
    assert source.read_text(encoding="utf-8") == "[Escape](escape/)\n"


def test_directory_fix_resolves_relative_to_nested_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs" / "with space").mkdir(parents=True)
    source = tmp_path / "docs" / "README.md"
    source.write_text('[Up](../) and [Space](<with space/> "title")\n', encoding="utf-8")

    assert main(["fix", "."]) == 0
    assert source.read_text(encoding="utf-8") == ('[Up](..) and [Space](<with space> "title")\n')
    assert main(["check", "."]) == 0
