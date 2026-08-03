"""Run Ruff's read-only formatting check."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOTS = ("src", "scripts", "tests")

def main() -> int:
    """Verify that the repository is formatted without rewriting files."""

    return subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--check",
            *PYTHON_ROOTS,
        ],
        cwd=ROOT,
        check=False,
    ).returncode

if __name__ == "__main__":
    raise SystemExit(main())
