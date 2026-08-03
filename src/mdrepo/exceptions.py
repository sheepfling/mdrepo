"""Structured exception matching and exception-health diagnostics."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from datetime import date

from pathspec import GitIgnoreSpec

from mdrepo.config import ApplicationConfig, ExceptionConfig
from mdrepo.models import Diagnostic

@dataclass(frozen=True, slots=True)
class ExceptionResult:
    """Visible, suppressed, and exception-health findings."""

    visible: tuple[Diagnostic, ...]
    suppressed: tuple[Diagnostic, ...]
    health: tuple[Diagnostic, ...]

def apply_exceptions(
        *,
        diagnostics: tuple[Diagnostic, ...],
        config: ApplicationConfig,
        today: date | None = None,
        report_unused: bool = True,
        enabled_rules: set[str] | None = None,
) -> ExceptionResult:
    """Suppress matching diagnostics and report expired or stale exception records."""

    current_date = today or date.today()
    active: list[ExceptionConfig] = []
    expired: list[ExceptionConfig] = []
    for exception in config.exceptions:
        if exception.expires is not None and exception.expires < current_date:
            expired.append(exception)
        else:
            active.append(exception)

    used: set[str] = set()
    visible: list[Diagnostic] = []
    suppressed: list[Diagnostic] = []
    for diagnostic in diagnostics:
        matched = next(
            (
                exception
                for exception in active
                if _matches(exception=exception, diagnostic=diagnostic)
            ),
            None,
        )
        if matched is None:
            visible.append(diagnostic)
            continue
        used.add(matched.id)
        suppressed.append(diagnostic.suppressed(matched.id))

    health: list[Diagnostic] = []
    if config.exception_policy.report_expired:
        for exception in expired:
            health.append(
                Diagnostic(
                    rule_id="MDR201",
                    message=(f"exception {exception.id!r} expired on {_expiry_text(exception)}"),
                    severity=config.exception_policy.expired_severity,
                    target=exception.id,
                    hint=f"Remove or renew it deliberately. Recorded reason: {exception.reason}",
                )
            )

    if config.exception_policy.report_unused and report_unused:
        for exception in active:
            if exception.id in used:
                continue
            if enabled_rules is not None and exception.rule not in enabled_rules:
                continue
            health.append(
                Diagnostic(
                    rule_id="MDR202",
                    message=f"exception {exception.id!r} did not suppress any finding",
                    severity=config.exception_policy.unused_severity,
                    target=exception.id,
                    hint=f"Remove the stale exception. Recorded reason: {exception.reason}",
                )
            )

    return ExceptionResult(
        visible=tuple(visible),
        suppressed=tuple(suppressed),
        health=tuple(health),
    )

def _expiry_text(exception: ExceptionConfig) -> str:
    if exception.expires is None:
        return "an unknown date"
    return exception.expires.isoformat()

def _matches(*, exception: ExceptionConfig, diagnostic: Diagnostic) -> bool:
    if exception.rule != diagnostic.rule_id:
        return False

    path_value = diagnostic.path.as_posix() if diagnostic.path is not None else "<project>"
    path_spec = GitIgnoreSpec.from_lines([exception.path])
    if not path_spec.match_file(path_value):
        return False

    if exception.target is not None:
        if diagnostic.target is None:
            return False
        if not fnmatch.fnmatchcase(diagnostic.target, exception.target):
            return False
    return True
