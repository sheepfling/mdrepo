"""Validate the repository's pre-commit configuration and hook manifest."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    """Validate both the self-use configuration and published hook manifest."""

    for command in (
            [sys.executable, "-m", "pre_commit", "validate-config", ".pre-commit-config.yaml"],
            [sys.executable, "-m", "pre_commit", "validate-manifest", ".pre-commit-hooks.yaml"],
    ):
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
