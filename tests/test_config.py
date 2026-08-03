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
