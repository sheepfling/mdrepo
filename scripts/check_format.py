"""Check Ruff formatting on marker-free temporary source copies."""

from __future__ import annotations

import subprocess
import sys
import tokenize
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOTS = (ROOT / "src", ROOT / "scripts", ROOT / "tests")
MARKERS = {"##", "####"}

def _without_standalone_markers(source: str) -> str:
    """Remove marker comments and their formatter-only padding."""

    lines = StringIO(source, newline="").readlines()
    marker_rows: set[int] = set()
    for token in tokenize.generate_tokens(StringIO(source).readline):
        if token.type != tokenize.COMMENT or token.string.strip() not in MARKERS:
            continue
        row, column = token.start
        line = lines[row - 1]
        if not line[:column].strip() and not line[token.end[1]:].strip():
            marker_rows.add(row - 1)
    if not marker_rows:
        return source

    padding_rows: set[int] = set()
    for marker_row in marker_rows:
        for direction in (-1, 1):
            row = marker_row + direction
            while 0 <= row < len(lines) and not lines[row].strip():
                padding_rows.add(row)
                row += direction

    unmarked = [(index, line) for index, line in enumerate(lines) if index not in marker_rows]
    newline = "\r\n" if "\r\n" in source else "\n"
    output: list[str] = []
    index = 0
    while index < len(unmarked):
        if unmarked[index][1].strip():
            output.append(unmarked[index][1])
            index += 1
            continue
        end = index
        while end < len(unmarked) and not unmarked[end][1].strip():
            end += 1
        blank_rows = unmarked[index:end]
        if not any(row in padding_rows for row, _ in blank_rows):
            output.extend(line for _, line in blank_rows)
        elif end == len(unmarked):
            pass
        else:
            previous = unmarked[index - 1][1] if index else ""
            following = unmarked[end][1]
            top_level_boundary = not previous.startswith((" ", "\t")) or not following.startswith(
                (" ", "\t")
            )
            output.extend([newline] * (2 if top_level_boundary else 1))
        index = end
    return "".join(output)

def _copy_unmarked_sources(destination: Path) -> None:
    """Copy source trees while removing Scope Marker comments."""

    for source_root in PYTHON_ROOTS:
        target_root = destination / source_root.relative_to(ROOT)
        for source in source_root.rglob("*.py"):
            target = target_root / source.relative_to(source_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            with tokenize.open(source) as stream:
                contents = _without_standalone_markers(stream.read())
                encoding = stream.encoding
            target.write_text(contents, encoding=encoding, newline="")

def main() -> int:
    """Verify Ruff formatting remains clean when markers are ignored."""

    with TemporaryDirectory(prefix="mdrepo-format-") as raw:
        destination = Path(raw)
        _copy_unmarked_sources(destination)
        check_command = [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--check",
            "--config",
            str(ROOT / "pyproject.toml"),
            str(destination / "src"),
            str(destination / "scripts"),
            str(destination / "tests"),
        ]
        return subprocess.run(check_command, cwd=ROOT, check=False).returncode

if __name__ == "__main__":
    raise SystemExit(main())
