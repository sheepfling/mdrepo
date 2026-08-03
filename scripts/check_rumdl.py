"""Run rumdl against the repository's Markdown documentation."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_ROOTS = ("README.md", "CHANGELOG.md", "docs")

def _rumdl_command() -> str:
    """Find rumdl in the active environment, including Windows Scripts."""

    executable = shutil.which("rumdl")
    if executable is not None:
        return executable
    sibling = Path(sys.executable).with_name("rumdl.exe")
    if sibling.exists():
        return str(sibling)
    sibling = sibling.with_name("rumdl")
    if sibling.exists():
        return str(sibling)
    raise FileNotFoundError(
        "rumdl is not installed; install the development dependencies with "
        '`python -m pip install -e ".[dev]"`'
    )

def main(argv: Sequence[str] = ()) -> int:
    """Check Markdown, optionally applying rumdl's safe fixes."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="apply rumdl's automatic fixes")
    args = parser.parse_args(argv)
    command = [_rumdl_command(), "check"]
    if args.fix:
        command.append("--fix")
    command.extend(MARKDOWN_ROOTS)
    return subprocess.run(command, cwd=ROOT, check=False).returncode

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
