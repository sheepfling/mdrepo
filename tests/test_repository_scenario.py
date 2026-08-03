"""End-to-end policy coverage for an interconnected pseudo repository."""

from pathlib import Path

import pytest

from mdrepo.cli import main


def test_interconnected_repository_reports_distinct_policy_issues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "Guide.md").write_text("[Next](next.md)\n", encoding="utf-8")
    (tmp_path / "docs" / "next.md").write_text("[Home](../README.md)\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.mdrepo.orphans]
enabled = true
roots = ["README.md"]
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        """[Portable](docs\\guide.md)
[Root](/docs/Guide.md)
[Machine](C:/docs/Guide.md)
[Escape](../outside.md)
""",
        encoding="utf-8",
    )

    assert main(["check", "."]) == 1
    output = capsys.readouterr().out

    for rule_id in ("MDR001", "MDR002", "MDR003", "MDR005"):
        assert rule_id in output
    assert "MDR101" not in output


def test_filtered_check_scopes_orphan_diagnostics(
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
    (tmp_path / "README.md").write_text("# Root\n", encoding="utf-8")
    (tmp_path / "orphan.md").write_text("# Orphan\n", encoding="utf-8")

    assert main(["check", "README.md"]) == 0
    assert "MDR101" not in capsys.readouterr().out

    assert main(["check", "."]) == 1
    assert "MDR101" in capsys.readouterr().out
