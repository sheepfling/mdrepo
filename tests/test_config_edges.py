"""Configuration normalization and override edge cases."""

from datetime import date

import pytest
from pydantic import ValidationError

from mdrepo.config import (
    ApplicationConfig,
    ConfigurationError,
    deep_merge,
    parse_override,
    set_dotted_value,
)
from mdrepo.models import Severity

@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("links.check_case=false", ("links.check_case", False)),
        ('rules.select=["MDR001", "MDR002"]', ("rules.select", ["MDR001", "MDR002"])),
        ("message=raw value", ("message", "raw value")),
        ("empty=", ("empty", "")),
    ],
)
def test_parse_override_accepts_typed_and_fallback_values(
        expression: str,
        expected: tuple[str, object],
) -> None:
    assert parse_override(expression) == expected

@pytest.mark.parametrize("expression", ("missing", "=value", "   =value"))
def test_parse_override_rejects_missing_or_blank_keys(expression: str) -> None:
    with pytest.raises(ConfigurationError, match="KEY=VALUE"):
        parse_override(expression)

def test_set_dotted_value_normalizes_underscores_and_rejects_scalar_parents() -> None:
    target: dict[str, object] = {}
    set_dotted_value(target, "rules.select", ["MDR001"])
    assert target == {"rules": {"select": ["MDR001"]}}

    with pytest.raises(ConfigurationError, match="configuration table"):
        set_dotted_value({"rules": "not-a-table"}, "rules.select", [])

    with pytest.raises(ConfigurationError, match="invalid dotted"):
        set_dotted_value({}, "rules..select", [])

def test_deep_merge_copies_nested_values_and_replaces_lists() -> None:
    base = {"links": {"check-case": True, "extensions": ["md"]}}
    overlay = {"links": {"require-posix": False, "extensions": ["markdown"]}}

    merged = deep_merge(base, overlay)
    assert merged == {
        "links": {
            "check-case": True,
            "require-posix": False,
            "extensions": ["markdown"],
        }
    }
    assert base == {"links": {"check-case": True, "extensions": ["md"]}}

def test_application_config_normalizes_rules_refs_extensions_and_exceptions() -> None:
    config = ApplicationConfig.model_validate(
        {
            "rules": {
                "select": ["mdr001, MDR002", "MDR001"],
                "severity": {" mdr001 ": "warning"},
            },
            "repository": {
                "provider": " GITHUB ",
                "relative_refs": ["/main/", "main", " feature/docs "],
            },
            "orphans": {"markdown_extensions": ["md", ".MARKDOWN", ""]},
            "exceptions": [
                {
                    "id": " temporary ",
                    "rule": "MDR101",
                    "reason": "Documented temporary exception.",
                    "expires": date(2027, 1, 1),
                }
            ],
        }
    )

    assert config.rules.select == ["MDR001", "MDR002"]
    assert config.rules.severity == {"MDR001": Severity.WARNING}
    assert config.repository.provider == "github"
    assert config.repository.relative_refs == ["main", "feature/docs"]
    assert config.orphans.markdown_extensions == [".md", ".markdown"]
    assert config.exceptions[0].id == "temporary"

@pytest.mark.parametrize(
    "payload",
    [
        {"repository": {"provider": "unknown"}},
        {"orphans": {"markdown_extensions": []}},
        {"exceptions": [{"id": "bad", "rule": "MDR201", "reason": "Not allowed."}]},
        {"exceptions": [{"id": "bad", "rule": "MDR101", "reason": "short"}]},
    ],
)
def test_application_config_rejects_invalid_policy_values(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ApplicationConfig.model_validate(payload)
