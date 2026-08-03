"""Configuration discovery, layering, and validation."""

from pathlib import Path

import pytest

from mdrepo.config import ConfigurationError, load_configuration
from mdrepo.models import OutputFormat, Severity

def test_pyproject_and_dedicated_overlay_merge(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.mdrepo]
fail-on = "warning"

[tool.mdrepo.links]
check-missing-targets = true
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / ".mdrepo.toml").write_text(
        """
[links]
check-case = false
""".strip(),
        encoding="utf-8",
    )

    loaded = load_configuration(
        cwd=tmp_path,
        root_override=None,
        config_paths=[],
        overrides=['output="json"'],
    )

    assert loaded.root == tmp_path
    assert loaded.model.fail_on is Severity.WARNING
    assert loaded.model.output is OutputFormat.JSON
    assert loaded.model.links.check_missing_targets is True
    assert loaded.model.links.check_case is False
    assert loaded.sources == (
        tmp_path / "pyproject.toml",
        tmp_path / ".mdrepo.toml",
    )

def test_external_overlay_does_not_change_discovered_root(tmp_path: Path) -> None:
    overlay = tmp_path.parent / f"{tmp_path.name}-overlay.toml"
    overlay.write_text("[links]\ncheck-case = false\n", encoding="utf-8")
    try:
        loaded = load_configuration(
            cwd=tmp_path,
            root_override=None,
            config_paths=[overlay],
            overrides=[],
        )
    finally:
        overlay.unlink()

    assert loaded.root == tmp_path
    assert loaded.model.links.check_case is False
    assert loaded.sources == (tmp_path / "pyproject.toml", overlay)

def test_unknown_configuration_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.mdrepo]\nunknown-option = true\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="unknown-option"):
        load_configuration(
            cwd=tmp_path,
            root_override=None,
            config_paths=[],
            overrides=[],
        )

def test_duplicate_exception_ids_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[[tool.mdrepo.exceptions]]
id = "same"
rule = "MDR101"
reason = "First documented exception."

[[tool.mdrepo.exceptions]]
id = "same"
rule = "MDR101"
reason = "Second documented exception."
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="exception IDs must be unique"):
        load_configuration(
            cwd=tmp_path,
            root_override=None,
            config_paths=[],
            overrides=[],
        )

def test_unknown_rule_id_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.mdrepo.rules]\nignore = ["MDR999"]\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="MDR999"):
        load_configuration(
            cwd=tmp_path,
            root_override=None,
            config_paths=[],
            overrides=[],
        )

def test_explicit_configuration_path_must_be_regular_file(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[tool.mdrepo]\n", encoding="utf-8")
    original_is_file = Path.is_file

    def pretend_non_regular(path: Path) -> bool:
        if path == config_path:
            return False
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", pretend_non_regular)

    with pytest.raises(ConfigurationError, match="not a regular file"):
        load_configuration(
            cwd=tmp_path,
            root_override=None,
            config_paths=[config_path],
            overrides=[],
        )
