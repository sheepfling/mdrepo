"""Safe fix application and line-ending preservation."""

from pathlib import Path

import pytest

from mdrepo.fixes import FixError, apply_fixes
from mdrepo.models import Fix, TextSpan


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
####




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
    ####
####


