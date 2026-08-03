"""Safe fix application and line-ending preservation."""

from pathlib import Path

import pytest

from mdrepo.fixes import FixError, apply_fixes, collect_fixes
from mdrepo.models import Diagnostic, Fix, Severity, TextSpan

def test_crlf_is_preserved_by_fix(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    original = "# Demo\r\n\r\n[Guide](docs\\guide.md)\r\n"
    path.write_bytes(original.encode())
    start = original.index("docs\\guide.md")
    fix = Fix(
        path=path,
        span=TextSpan(start=start, end=start + len("docs\\guide.md"), line=3, column=9),
        expected="docs\\guide.md",
        replacement="docs/guide.md",
        description="normalize separators",
    )

    result = apply_fixes(
        fixes=(fix,),
        root=tmp_path,
        encoding="utf-8",
        dry_run=False,
    )

    assert result.applied_count == 1
    assert path.read_bytes() == original.replace("docs\\guide.md", "docs/guide.md").encode()
    assert b"\r\n" in path.read_bytes()

def test_stale_source_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("changed", encoding="utf-8")
    fix = Fix(
        path=path,
        span=TextSpan(start=0, end=4, line=1, column=1),
        expected="old!",
        replacement="new!",
        description="test",
    )

    with pytest.raises(FixError, match="source changed after analysis"):
        apply_fixes(
            fixes=(fix,),
            root=tmp_path,
            encoding="utf-8",
            dry_run=False,
        )

def test_collect_fixes_deduplicates_identical_spans_and_rejects_conflicts(
        tmp_path: Path,
) -> None:
    path = tmp_path / "README.md"
    span = TextSpan(start=0, end=4, line=1, column=1)
    fix = Fix(
        path=path,
        span=span,
        expected="old!",
        replacement="new!",
        description="replace",
    )
    diagnostic = Diagnostic(rule_id="MDR001", message="one", severity=Severity.ERROR, fix=fix)
    duplicate = Diagnostic(
        rule_id="MDR005",
        message="two",
        severity=Severity.ERROR,
        fix=fix,
    )

    assert collect_fixes((diagnostic, duplicate)) == (fix,)

    conflicting = Fix(
        path=path,
        span=span,
        expected="old!",
        replacement="other",
        description="conflict",
    )
    with pytest.raises(FixError, match="conflicting fixes"):
        collect_fixes(
            (
                diagnostic,
                Diagnostic(
                    rule_id="MDR002",
                    message="conflict",
                    severity=Severity.ERROR,
                    fix=conflicting,
                ),
            )
        )

def test_collect_fixes_rejects_overlapping_spans(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    first = Fix(
        path=path,
        span=TextSpan(start=0, end=5, line=1, column=1),
        expected="first",
        replacement="one",
        description="first",
    )
    second = Fix(
        path=path,
        span=TextSpan(start=4, end=8, line=1, column=5),
        expected="second",
        replacement="two",
        description="second",
    )

    with pytest.raises(FixError, match="overlapping fixes"):
        collect_fixes(
            (
                Diagnostic(rule_id="MDR001", message="first", severity=Severity.ERROR, fix=first),
                Diagnostic(
                    rule_id="MDR002",
                    message="second",
                    severity=Severity.ERROR,
                    fix=second,
                ),
            )
        )

def test_dry_run_returns_diff_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("[Guide](docs\\guide.md)\n", encoding="utf-8")
    fix = Fix(
        path=path,
        span=TextSpan(start=8, end=21, line=1, column=9),
        expected="docs\\guide.md",
        replacement="docs/guide.md",
        description="normalize separators",
    )

    result = apply_fixes(fixes=(fix,), root=tmp_path, encoding="utf-8", dry_run=True)

    assert result.applied_count == 1
    assert result.changed_files == (path,)
    assert "docs\\guide.md" in result.diffs[0]
    assert "docs/guide.md" in result.diffs[0]
    assert path.read_text(encoding="utf-8") == "[Guide](docs\\guide.md)\n"
