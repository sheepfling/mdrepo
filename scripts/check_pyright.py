"""Run the repository's strict Pyright check."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    """Run Pyright using the active development environment."""

    return subprocess.run(
        [sys.executable, "-m", "pyright", "--pythonpath", sys.executable],
        cwd=ROOT,
        check=False,
    ).returncode

if __name__ == "__main__":
    raise SystemExit(main())
