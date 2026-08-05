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


def test_application_config_normalizes_rules_extensions_and_exceptions() -> None:
    config = ApplicationConfig.model_validate(
        {
            "rules": {
                "select": ["mdr001, MDR002", "MDR001"],
                "severity": {" mdr001 ": "warning"},
            },
            "orphans": {"markdown_extensions": ["md", ".MARKDOWN", ""]},
            "exceptions": [
                {
                    "id": " temporary ",
                    "rule": " mdr101 ",
                    "reason": "Documented temporary exception.",
                    "expires": date(2027, 1, 1),
                }
            ],
        }
    )

    assert config.rules.select == ["MDR001", "MDR002"]
    assert config.rules.severity == {"MDR001": Severity.WARNING}
    assert config.orphans.markdown_extensions == [".md", ".markdown"]
    assert config.exceptions[0].id == "temporary"
    assert config.exceptions[0].rule == "MDR101"


def test_application_config_preserves_exclude_order_and_repetitions() -> None:
    config = ApplicationConfig.model_validate({"exclude": ["**/dist/**", "notes/**", "notes/**"]})

    assert config.exclude.count("**/dist/**") == 2
    assert config.exclude.count("notes/**") == 2
    assert "**/__pycache__/**" in config.exclude
    assert config.exclude[-3:] == ["**/dist/**", "notes/**", "notes/**"]


@pytest.mark.parametrize(
    "payload",
    [
        {"orphans": {"markdown_extensions": []}},
        {"exceptions": [{"id": "bad", "rule": "MDR201", "reason": "Not allowed."}]},
        {"exceptions": [{"id": "bad", "rule": "MDR101", "reason": "short"}]},
        {"exceptions": [{"id": "bad", "rule": "MDR101", "reason": "       a"}]},
    ],
)
def test_application_config_rejects_invalid_policy_values(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ApplicationConfig.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [("id", 123), ("rule", 101), ("path", ["**"]), ("reason", None)],
)
def test_exception_fields_preserve_type_validation(
    field: str,
    value: object,
) -> None:
    payload: dict[str, object] = {
        "id": "exception",
        "rule": "MDR101",
        "path": "**",
        "reason": "A sufficiently documented reason.",
        field: value,
    }
    with pytest.raises(ValidationError):
        ApplicationConfig.model_validate({"exceptions": [payload]})


@pytest.mark.parametrize(
    "payload",
    [
        {"rules": {"select": [123]}},
        {"rules": {"ignore": [None]}},
        {"rules": {"severity": {123: "warning"}}},
        {"orphans": {"markdown_extensions": [123]}},
        {"exceptions": [{"id": "id", "rule": "MDR101", "path": 123}]},
        {"exceptions": [{"id": "id", "rule": "MDR101", "target": ["path"]}]},
    ],
)
def test_all_normalizers_preserve_non_string_type_validation(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ApplicationConfig.model_validate(payload)
