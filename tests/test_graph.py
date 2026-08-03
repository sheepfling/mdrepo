"""Rooted document graph and orphan behavior."""

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
####




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
####




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
####


