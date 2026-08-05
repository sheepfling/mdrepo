"""Portable local-link policy and safe fixes."""

from pathlib import Path

import pytest

from mdrepo.cli import main


def test_backslash_and_case_are_combined_into_one_safe_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "Guide.md").write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("[Guide](docs\\guide.md)\n", encoding="utf-8")

    assert main(["check", "."]) == 1
    output = capsys.readouterr().out
    assert "MDR001" in output
    assert "MDR005" in output

    assert main(["fix", "."]) == 0
    capsys.readouterr()
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "[Guide](docs/Guide.md)\n"


def test_root_relative_link_is_fixed_when_target_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("[Guide](/docs/guide.md)\n", encoding="utf-8")

    assert main(["fix", "."]) == 0
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "[Guide](docs/guide.md)\n"


def test_fix_does_not_rewrite_prose_before_the_actual_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    original = "Mention (docs\\guide.md), then [Guide](docs\\guide.md)\n"
    (tmp_path / "README.md").write_text(original, encoding="utf-8")

    assert main(["fix", "."]) == 0
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == (
        "Mention (docs\\guide.md), then [Guide](docs/guide.md)\n"
    )


def test_windows_absolute_and_repository_escape_are_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text(
        "[Windows](C:/temp/file.md)\n[Escape](../outside.md)\n",
        encoding="utf-8",
    )

    assert main(["check", "."]) == 1
    output = capsys.readouterr().out
    assert "MDR002" in output
    assert "MDR003" in output


def test_home_relative_destination_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("[Home](~/docs/guide.md)\n", encoding="utf-8")

    assert main(["check", "."]) == 1
    output = capsys.readouterr().out
    assert "MDR002" in output
    assert "home-relative" in output


def test_missing_target_check_is_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("[Missing](docs/nope.md)\n", encoding="utf-8")

    assert main(["check", "."]) == 0
    assert "MDR004" not in capsys.readouterr().out

    assert main(["check", ".", "--set", "links.check-missing-targets=true"]) == 1
    assert "MDR004" in capsys.readouterr().out


def test_existing_gitignored_and_mdrepo_excluded_targets_are_not_durable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_text("scratch/\n", encoding="utf-8")
    (tmp_path / "scratch").mkdir()
    (tmp_path / "scratch" / "guide.md").write_text("# Scratch\n", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "artifact.md").write_text("# Build\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "[Scratch](scratch/guide.md)\n[Build](build/artifact.md)\n",
        encoding="utf-8",
    )

    assert main(["check", "."]) == 1
    output = capsys.readouterr().out
    assert output.count("MDR006") == 2
    assert ".gitignore" in output
    assert "mdrepo exclude policy" in output


def test_durable_target_check_can_be_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_text("scratch/\n", encoding="utf-8")
    (tmp_path / "scratch").mkdir()
    (tmp_path / "scratch" / "guide.md").write_text("# Scratch\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("[Scratch](scratch/guide.md)\n", encoding="utf-8")

    assert main(["check", ".", "--set", "links.check-durable-targets=false"]) == 0
    assert "MDR006" not in capsys.readouterr().out


def test_nested_gitignore_also_marks_existing_target_non_durable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / ".gitignore").write_text("drafts/\n", encoding="utf-8")
    (tmp_path / "docs" / "drafts").mkdir()
    (tmp_path / "docs" / "drafts" / "guide.md").write_text(
        "# Draft\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "[Draft](docs/drafts/guide.md)\n",
        encoding="utf-8",
    )

    assert main(["check", "."]) == 1
    assert "MDR006" in capsys.readouterr().out


def test_reference_definition_is_fixed_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "Guide.md").write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "[One][guide] and [Two][guide]\n\n[guide]: docs\\guide.md\n",
        encoding="utf-8",
    )

    assert main(["fix", "."]) == 0
    assert "[guide]: docs/Guide.md" in (tmp_path / "README.md").read_text(encoding="utf-8")
