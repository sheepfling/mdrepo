"""Conflict-checked safe source edits."""

from __future__ import annotations

import difflib
import os
import stat
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from mdrepo.models import Diagnostic, Fix

class FixError(RuntimeError):
    """Raised when safe edits overlap, become stale, or cannot be written."""

@dataclass(frozen=True, slots=True)
class FixResult:
    """Summary of one applied or dry-run fix plan."""

    applied_count: int
    changed_files: tuple[Path, ...]
    diffs: tuple[str, ...]

def collect_fixes(diagnostics: tuple[Diagnostic, ...]) -> tuple[Fix, ...]:
    """Collect and de-duplicate safe edits attached to visible diagnostics."""

    unique: dict[tuple[Path, int, int], Fix] = {}
    for diagnostic in diagnostics:
        fix = diagnostic.fix
        if fix is None:
            continue
        key = (fix.path, fix.span.start, fix.span.end)
        existing = unique.get(key)
        if existing is None:
            unique[key] = fix
            continue
        if existing.expected != fix.expected or existing.replacement != fix.replacement:
            raise FixError(
                "conflicting fixes target the same source span: "
                f"{fix.path}:{fix.span.line}:{fix.span.column}"
            )

    ordered = tuple(
        sorted(
            unique.values(),
            key=lambda candidate_fix: (
                str(candidate_fix.path),
                candidate_fix.span.start,
                candidate_fix.span.end,
            ),
        )
    )
    _validate_non_overlapping(ordered)
    return ordered

def apply_fixes(
        *,
        fixes: tuple[Fix, ...],
        root: Path,
        encoding: str,
        dry_run: bool,
) -> FixResult:
    """Apply safe edits atomically per file or return unified diffs without writing."""

    grouped: dict[Path, list[Fix]] = {}
    for fix in fixes:
        grouped.setdefault(fix.path, []).append(fix)

    changed_files: list[Path] = []
    diffs: list[str] = []
    for path in sorted(grouped):
        try:
            original = path.read_bytes().decode(encoding)
        except (OSError, UnicodeError) as error:
            raise FixError(f"unable to read fix target {path}: {error}") from error

        updated = original
        for fix in sorted(grouped[path], key=lambda item: item.span.start, reverse=True):
            actual = updated[fix.span.start: fix.span.end]
            if actual != fix.expected:
                raise FixError(
                    "source changed after analysis at "
                    f"{path}:{fix.span.line}:{fix.span.column}; "
                    f"expected {fix.expected!r}, found {actual!r}"
                )
            updated = updated[: fix.span.start] + fix.replacement + updated[fix.span.end:]

        if updated == original:
            continue
        changed_files.append(path)
        relative = path.relative_to(root).as_posix()
        diffs.append(
            "".join(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    updated.splitlines(keepends=True),
                    fromfile=f"a/{relative}",
                    tofile=f"b/{relative}",
                )
            )
        )
        if not dry_run:
            _atomic_write(path=path, text=updated, encoding=encoding)

    return FixResult(
        applied_count=len(fixes),
        changed_files=tuple(changed_files),
        diffs=tuple(diffs),
    )

def _validate_non_overlapping(fixes: tuple[Fix, ...]) -> None:
    previous_by_path: dict[Path, Fix] = {}
    for fix in fixes:
        previous = previous_by_path.get(fix.path)
        if previous is not None and fix.span.start < previous.span.end:
            raise FixError(
                "overlapping fixes are not safe to apply: "
                f"{fix.path}:{previous.span.line} and {fix.span.line}"
            )
        previous_by_path[fix.path] = fix

def _atomic_write(*, path: Path, text: str, encoding: str) -> None:
    temporary_path: Path | None = None
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(text.encode(encoding))
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    except (OSError, UnicodeError) as error:
        if temporary_path is not None:
            with suppress(OSError):
                temporary_path.unlink(missing_ok=True)
        raise FixError(f"unable to write fixed Markdown file {path}: {error}") from error
