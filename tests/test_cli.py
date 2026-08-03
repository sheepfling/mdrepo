"""CLI placement, formats, and exit behavior."""

import json
from pathlib import Path

import pytest

from mdrepo.cli import main


def test_global_options_work_before_or_after_subcommand(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path.parent)

    assert main(["--root", str(tmp_path), "check"]) == 0
    assert main(["check", "--root", str(tmp_path)]) == 0
####




def test_json_diagnostic_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("[Root](/README.md)\n", encoding="utf-8")

    assert main(["check", ".", "--format", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["rule_id"] == "MDR002"
    assert payload[0]["fix"]["replacement"] == "README.md"
####




def test_select_and_ignore_rules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("[Root](/README.md)\n", encoding="utf-8")

    assert main(["check", ".", "--ignore", "MDR002"]) == 0
    assert capsys.readouterr().out == ""

    assert main(["check", ".", "--select", "MDR002"]) == 1
    assert "MDR002" in capsys.readouterr().out
####


