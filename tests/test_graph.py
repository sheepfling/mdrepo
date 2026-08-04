"""Rooted document graph and orphan behavior."""

import json
from pathlib import Path

import pytest

from mdrepo.cli import main


def test_orphan_graph_follows_reference_and_extensionless_links(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.mdrepo.orphans]
enabled = true
roots = ["README.md"]
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("[Guide][guide]\n\n[guide]: docs/guide\n", encoding="utf-8")
    (tmp_path / "docs" / "guide.md").write_text("[More](more.md)\n", encoding="utf-8")
    (tmp_path / "docs" / "more.md").write_text("# More\n", encoding="utf-8")
    (tmp_path / "orphan.md").write_text("# Orphan\n", encoding="utf-8")

    assert main(["check", "."]) == 1
    output = capsys.readouterr().out
    assert "orphan.md" in output
    assert "docs/guide.md" not in output
    assert "docs/more.md" not in output


def test_orphan_can_be_governed_by_structured_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.mdrepo.orphans]
enabled = true
roots = ["README.md"]

[[tool.mdrepo.exceptions]]
id = "standalone-changelog"
rule = "MDR101"
path = "CHANGELOG.md"
reason = "The changelog is discovered by package tooling instead."
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Root\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")

    assert main(["check", ".", "--show-suppressed"]) == 0
    output = capsys.readouterr().out
    assert "suppressed by: standalone-changelog" in output


def test_gitignored_documents_do_not_enter_orphan_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.mdrepo.orphans]
enabled = true
roots = ["README.md"]
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / ".gitignore").write_text("generated.md\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Root\n", encoding="utf-8")
    (tmp_path / "generated.md").write_text("[Guide](guide.md)\n", encoding="utf-8")
    (tmp_path / "guide.md").write_text("# Guide\n", encoding="utf-8")

    assert main(["check", "."]) == 1
    output = capsys.readouterr().out
    assert "guide.md" in output
    assert "generated.md" not in output


def test_respecting_gitignore_removes_ignored_sources_but_keeps_durability_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.mdrepo]
respect-gitignore = true

[tool.mdrepo.orphans]
enabled = true
roots = ["README.md"]
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / ".gitignore").write_text("generated.md\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("[Generated](generated.md)\n", encoding="utf-8")
    (tmp_path / "generated.md").write_text("[Bad](docs\\guide.md)\n", encoding="utf-8")

    assert main(["check", "."]) == 1
    output = capsys.readouterr().out
    assert "MDR006" in output
    assert "MDR001" not in output


def test_graph_command_emits_dot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("[Guide](guide.md)\n", encoding="utf-8")
    (tmp_path / "guide.md").write_text("# Guide\n", encoding="utf-8")

    assert main(["graph", "--graph-format", "dot"]) == 0
    output = capsys.readouterr().out
    assert '"README.md" -> "guide.md";' in output


def test_graph_resolves_directory_indexes_and_cycles_without_orphans(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text(
        "![Logo](assets/logo.png)\n[Docs](docs/)\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "index.md").write_text("[Back](../README.md)\n", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(b"image")

    assert main(["graph", "--graph-format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["edges"]["README.md"] == ["docs/index.md"]
    assert payload["edges"]["docs/index.md"] == ["README.md"]
    assert payload["unreachable"] == []


def test_enabled_orphan_check_reports_missing_configured_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.mdrepo.orphans]
enabled = true
roots = ["docs/index.md"]
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Root\n", encoding="utf-8")

    assert main(["check", "."]) == 1
    output = capsys.readouterr().out
    assert "MDR100" in output
    assert "docs/index.md" in output
