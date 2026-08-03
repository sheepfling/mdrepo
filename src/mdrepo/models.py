"""Immutable models shared by parsing, rules, reporting, and fixes."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path


class Severity(StrEnum):
    """Diagnostic severity."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
####




class OutputFormat(StrEnum):
    """Supported diagnostic output formats."""

    TEXT = "text"
    JSON = "json"
    GITHUB = "github"
####




class LinkKind(StrEnum):
    """Markdown construct that uses a destination."""

    LINK = "link"
    IMAGE = "image"
    REFERENCE_DEFINITION = "reference-definition"
####




class LinkSourceKind(StrEnum):
    """How a parsed destination is represented in source Markdown."""

    DIRECT = "direct"
    AUTOLINK = "autolink"
    REFERENCE_USE = "reference-use"
    REFERENCE_DEFINITION = "reference-definition"
####




@dataclass(frozen=True, slots=True)
class TextSpan:
    """Half-open character range in a UTF-8-decoded source string."""

    start: int
    end: int
    line: int
    column: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid text span: {self.start}:{self.end}")
        ####
        if self.line < 1 or self.column < 1:
            raise ValueError("line and column must be one-based positive integers")
        ####
    ####
####





@dataclass(frozen=True, slots=True)
class Fix:
    """One safe, source-level replacement."""

    path: Path
    span: TextSpan
    expected: str
    replacement: str
    description: str
####




@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One repository policy finding."""

    rule_id: str
    message: str
    severity: Severity
    path: Path | None = None
    line: int | None = None
    column: int | None = None
    target: str | None = None
    hint: str | None = None
    fix: Fix | None = None
    suppressed_by: str | None = None

    def with_severity(self, severity: Severity) -> Diagnostic:
        """Return a copy with a configured severity override."""

        return replace(self, severity=severity)
    ####


    def suppressed(self, exception_id: str) -> Diagnostic:
        """Return a copy marked as suppressed by one named exception."""

        return replace(self, suppressed_by=exception_id, fix=None)
    ####
####





@dataclass(frozen=True, slots=True)
class RuleMetadata:
    """Stable public metadata for one built-in rule."""

    rule_id: str
    name: str
    description: str
    default_severity: Severity
    fixable: bool
####




@dataclass(frozen=True, slots=True)
class LinkOccurrence:
    """One parsed Markdown destination or reference definition."""

    target: str
    raw_target: str
    kind: LinkKind
    source_kind: LinkSourceKind
    line: int
    column: int | None
    span: TextSpan | None
    reference_label: str | None = None

    @property
    def can_edit(self) -> bool:
        """Return whether the destination has an exact source span."""

        return self.span is not None
    ####
####





@dataclass(frozen=True, slots=True)
class Document:
    """One parsed Markdown file."""

    path: Path
    relative_path: Path
    text: str
    links: tuple[LinkOccurrence, ...]
    reference_definitions: tuple[LinkOccurrence, ...]

    @property
    def policy_occurrences(self) -> tuple[LinkOccurrence, ...]:
        """Return destinations that own editable policy text.

        Reference uses inherit their destination from a definition. The definition is checked once
        instead of reporting the same problem at every use site.
        """

        direct = tuple(
            occurrence
            for occurrence in self.links
            if occurrence.source_kind is not LinkSourceKind.REFERENCE_USE
        )
        return direct + self.reference_definitions
    ####
####



