"""Stable text, JSON, and GitHub Actions reporting."""

from __future__ import annotations

import json
from typing import Protocol

from mdrepo.models import Diagnostic, OutputFormat, Severity

_SEVERITY_RANK = {
    Severity.INFO: 0,
    Severity.WARNING: 1,
    Severity.ERROR: 2,
}


class TextWriter(Protocol):
    """Minimal structural interface required by diagnostic renderers."""

    def write(self, text: str, /) -> int:
        """Write text and return the number of characters accepted."""

        ...


def write_diagnostics(
    *,
    diagnostics: tuple[Diagnostic, ...],
    output_format: OutputFormat,
    stream: TextWriter,
) -> None:
    """Render diagnostics in one deterministic output format."""

    if output_format is OutputFormat.JSON:
        json.dump(
            [_json_record(diagnostic) for diagnostic in diagnostics],
            stream,
            indent=2,
            sort_keys=True,
        )
        stream.write("\n")
        return

    if output_format is OutputFormat.GITHUB:
        for diagnostic in diagnostics:
            stream.write(_github_line(diagnostic) + "\n")
        return

    for diagnostic in diagnostics:
        stream.write(_text_line(diagnostic) + "\n")
        if diagnostic.hint:
            stream.write(f"  hint: {diagnostic.hint}\n")
        if diagnostic.fix is not None:
            stream.write(f"  fix: {diagnostic.fix.description}\n")
        if diagnostic.suppressed_by is not None:
            stream.write(f"  suppressed by: {diagnostic.suppressed_by}\n")


def should_fail(*, diagnostics: tuple[Diagnostic, ...], threshold: Severity) -> bool:
    """Return whether any visible diagnostic meets the configured failure threshold."""

    minimum = _SEVERITY_RANK[threshold]
    return any(_SEVERITY_RANK[diagnostic.severity] >= minimum for diagnostic in diagnostics)


def _text_line(diagnostic: Diagnostic) -> str:
    return (
        f"{_location(diagnostic)}: {diagnostic.severity.value} "
        f"{diagnostic.rule_id} {diagnostic.message}"
    )


def _location(diagnostic: Diagnostic) -> str:
    rendered = diagnostic.path.as_posix() if diagnostic.path is not None else "<project>"
    if diagnostic.line is not None:
        rendered += f":{diagnostic.line}"
    if diagnostic.column is not None:
        rendered += f":{diagnostic.column}"
    return rendered


def _json_record(diagnostic: Diagnostic) -> dict[str, object]:
    fix: dict[str, object] | None = None
    edit = diagnostic.fix
    if edit is not None:
        fix = {
            "description": edit.description,
            "end": edit.span.end,
            "expected": edit.expected,
            "replacement": edit.replacement,
            "start": edit.span.start,
        }
    return {
        "column": diagnostic.column,
        "fix": fix,
        "hint": diagnostic.hint,
        "line": diagnostic.line,
        "message": diagnostic.message,
        "path": diagnostic.path.as_posix() if diagnostic.path is not None else None,
        "rule_id": diagnostic.rule_id,
        "severity": diagnostic.severity.value,
        "suppressed_by": diagnostic.suppressed_by,
        "target": diagnostic.target,
    }


def _github_line(diagnostic: Diagnostic) -> str:
    command = {
        Severity.ERROR: "error",
        Severity.WARNING: "warning",
        Severity.INFO: "notice",
    }[diagnostic.severity]
    fields: list[str] = []
    if diagnostic.path is not None:
        fields.append(f"file={_github_escape_property(diagnostic.path.as_posix())}")
    if diagnostic.line is not None:
        fields.append(f"line={diagnostic.line}")
    if diagnostic.column is not None:
        fields.append(f"col={diagnostic.column}")
    fields.append(f"title={_github_escape_property(diagnostic.rule_id)}")
    properties = ",".join(fields)
    message = _github_escape_data(diagnostic.message)
    return f"::{command} {properties}::{message}"


def _github_escape_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _github_escape_property(value: str) -> str:
    return _github_escape_data(value).replace(":", "%3A").replace(",", "%2C")
