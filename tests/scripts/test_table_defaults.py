"""Keep the repository and its adoption examples usable as table-formatting templates."""

import shutil
import subprocess
from pathlib import Path

import pytest

from mdrepo._compat import tomllib
from tests.scripts.test_documentation_contracts import ROOT, TOML_FENCE


def _rumdl_configs() -> list[str]:
    configs = [(ROOT / "pyproject.toml").read_text(encoding="utf-8")]
    for name in ("adopting.md", "ci-integration.md"):
        text = (ROOT / "docs" / name).read_text(encoding="utf-8")
        examples = [match.group("body") for match in TOML_FENCE.finditer(text)]
        configs.extend(body for body in examples if "[tool.rumdl]" in body)
    assert len(configs) == 3
    return configs


@pytest.mark.parametrize("config", _rumdl_configs(), ids=("repository", "adoption", "ci"))
def test_table_defaults_align_wide_tables_and_check_prose(config: str, tmp_path: Path) -> None:
    settings = tomllib.loads(config)["tool"]["rumdl"]
    assert "MD060" in settings["extend-enable"]
    assert settings["MD060"]["style"] == "aligned"
    assert settings["MD013"]["tables"] is False
    config_path = tmp_path / "pyproject.toml"
    config_path.write_text(config, encoding="utf-8")
    document = tmp_path / "table.md"
    wide_cell = "wide cell " * 14
    original = f"# Table\n\n| Short | Value |\n| :--- | ---: |\n| tiny | {wide_cell.strip()} |\n"
    document.write_text(original, encoding="utf-8")
    executable = shutil.which("rumdl")
    assert executable is not None, "Install the rumdl development dependency before running tests"
    command = [executable, "check", "--config", str(config_path), str(document)]

    def run(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*command, *arguments], cwd=tmp_path, capture_output=True, text=True, check=False
        )

    before = run()
    assert before.returncode == 1, before.stdout + before.stderr
    assert "MD060" in before.stdout
    assert document.read_text(encoding="utf-8") == original
    fixed = run("--fix")
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    aligned = document.read_text(encoding="utf-8")
    rows = [line for line in aligned.splitlines() if line.startswith("|")]
    pipe_positions = [{index for index, char in enumerate(row) if char == "|"} for row in rows]
    assert len(rows) == 3
    assert pipe_positions[0] == pipe_positions[1] == pipe_positions[2]
    assert len(rows[0]) > 100
    assert rows[1].startswith("| :") and rows[1].endswith(": |")
    assert wide_cell.strip() in rows[2]
    clean = run()
    assert clean.returncode == 0, clean.stdout + clean.stderr
    second_fix = run("--fix")
    assert second_fix.returncode == 0, second_fix.stdout + second_fix.stderr
    assert document.read_text(encoding="utf-8") == aligned

    document.write_text(aligned + "\n" + "Ordinary prose " * 12 + "ends here.\n", encoding="utf-8")
    prose = run()
    assert prose.returncode == 1, prose.stdout + prose.stderr
    assert "MD013" in prose.stdout
    assert "MD060" not in prose.stdout
