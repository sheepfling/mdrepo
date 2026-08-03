"""Build clean PyPI artifacts in an isolated temporary output directory."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    """Verify both wheel and source-distribution packaging."""

    with TemporaryDirectory(prefix="mdrepo-build-") as output:
        build_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--sdist",
                "--wheel",
                "--outdir",
                output,
            ],
            cwd=ROOT,
            check=False,
        )
        if build_result.returncode:
            return build_result.returncode
        distributions = sorted(Path(output).glob("*"))
        return subprocess.run(
            [sys.executable, "-m", "twine", "check", *(str(path) for path in distributions)],
            cwd=ROOT,
            check=False,
        ).returncode

if __name__ == "__main__":
    raise SystemExit(main())
