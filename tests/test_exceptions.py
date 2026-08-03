"""Structured exception lifecycle."""

from datetime import date
from pathlib import Path

import pytest

from mdrepo.cli import main
from mdrepo.config import ApplicationConfig
from mdrepo.exceptions import apply_exceptions
from mdrepo.models import Diagnostic, Severity

def test_expired_exception_does_not_suppress() -> None:
    config = ApplicationConfig.model_validate(
        {
            "exceptions": [
                {
                    "id": "old",
                    "rule": "MDR101",
                    "path": "archive.md",
                    "reason": "Temporary archive exception.",
                    "expires": date(2026, 1, 1),
                }
            ]
        }
    )
    diagnostic = Diagnostic(
        rule_id="MDR101",
        message="orphan",
        severity=Severity.ERROR,
        path=Path("archive.md"),
    )

    result = apply_exceptions(
        diagnostics=(diagnostic,),
        config=config,
        today=date(2026, 8, 2),
    )

    assert result.visible == (diagnostic,)
    assert result.suppressed == ()
    assert [item.rule_id for item in result.health] == ["MDR201"]

def test_unused_exception_is_not_reported_during_partial_run() -> None:
    config = ApplicationConfig.model_validate(
        {
            "exceptions": [
                {
                    "id": "future",
                    "rule": "MDR101",
                    "path": "archive.md",
                    "reason": "Known standalone archive document.",
                }
            ]
        }
    )

    result = apply_exceptions(
        diagnostics=(),
        config=config,
        report_unused=False,
        enabled_rules={"MDR101"},
    )

    assert result.health == ()

def test_full_directory_check_reports_unused_exception(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("# Root\n", encoding="utf-8")
    (tmp_path / "docs" / "standalone.md").write_text("# Standalone\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.mdrepo]

[[tool.mdrepo.exceptions]]
id = "removed-workaround"
rule = "MDR101"
path = "docs/standalone.md"
reason = "The old workaround is no longer needed."
""".strip(),
        encoding="utf-8",
    )

    assert main(["check", "."]) == 0
    assert "MDR202" in capsys.readouterr().out

    assert main(["check", "README.md"]) == 0
    assert "MDR202" not in capsys.readouterr().out
