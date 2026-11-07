"""Mechanical checks for the documentation's version and configuration contracts."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from mdrepo.config import ApplicationConfig

ROOT = Path(__file__).resolve().parents[2]
DOCUMENTATION_FILES = (ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md")))
VERSION_PIN = re.compile(r"mdrepo==([0-9][^\s\"'`,)]*)")
TOML_FENCE = re.compile(r"```toml\n(?P<body>.*?)```", re.DOTALL)
EXAMPLE_MARKER = "# mdrepo-doc-example"


def _documentation_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in DOCUMENTATION_FILES)


def test_documented_release_pins_are_consistent() -> None:
    pins = VERSION_PIN.findall(_documentation_text())

    assert pins
    assert len(set(pins)) == 1


def test_documented_defaults_match_configuration_models() -> None:
    application = ApplicationConfig()
    documentation = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")

    respect_gitignore = str(application.respect_gitignore).lower()
    assert f"| `respect-gitignore` | `{respect_gitignore}`" in documentation
    assert (
        f"`check-missing-targets = {str(application.links.check_missing_targets).lower()}`"
        in documentation
    )
    durable_default = "enabled" if application.links.check_durable_targets else "disabled"
    assert "`check-durable-targets` enables `MDR006`" in documentation
    assert f"{durable_default} by default" in documentation
    orphan_default = "enabled" if application.orphans.enabled else "disabled"
    assert f"Orphan analysis is {orphan_default} by default." in documentation

    match = re.search(r"```toml\n(?P<body>exclude = \[.*?\])\n```", documentation, re.DOTALL)
    assert match
    documented_exclude = tomllib.loads(match.group("body"))["exclude"]
    assert documented_exclude == application.exclude


def test_marked_toml_examples_validate_as_mdrepo_configuration() -> None:
    examples: list[tuple[Path, dict[str, Any]]] = []
    for path in DOCUMENTATION_FILES:
        text = path.read_text(encoding="utf-8")
        for match in TOML_FENCE.finditer(text):
            body = match.group("body")
            if EXAMPLE_MARKER not in body:
                continue
            parsed = tomllib.loads(body)
            tool_table = parsed.get("tool")
            assert isinstance(tool_table, dict), path
            typed_tool_table = cast(dict[str, Any], tool_table)
            mdrepo_table = cast(dict[str, Any] | None, typed_tool_table.get("mdrepo"))
            assert isinstance(mdrepo_table, dict), path
            examples.append((path, mdrepo_table))

    assert examples
    for path, mdrepo_table in examples:
        try:
            ApplicationConfig.model_validate(mdrepo_table)
        except ValidationError as error:
            raise AssertionError(f"invalid mdrepo TOML example in {path}") from error
