"""Build clean PyPI artifacts in an isolated temporary output directory."""

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import suppress
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from shutil import copytree, ignore_patterns
from tempfile import TemporaryDirectory

from mdrepo._metadata import DISTRIBUTION_NAME as PACKAGE_NAME
from mdrepo._metadata import SCM_VERSION_ENV

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Verify both wheel and source-distribution packaging."""

    ignored = ignore_patterns(
        ".git",
        ".venv*",
        ".codex_pydeps",
        ".pip-cache",
        ".pre-commit-cache",
        ".pytest_cache",
        ".ruff_cache",
        ".rumdl_cache",
        ".tmp",
        "__pycache__",
        "build",
        "dist",
        "*.egg-info",
        ".coverage",
        ".idea",
        "inbox",
    )
    with TemporaryDirectory(prefix="mdrepo-build-") as temporary:
        temporary_root = Path(temporary)
        source = temporary_root / "source"
        output = temporary_root / "dist"
        copytree(ROOT, source, ignore=ignored)
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
            cwd=source,
            env=_build_environment(),
            check=False,
        )
        if build_result.returncode:
            return build_result.returncode
        distributions = [
            path
            for path in sorted(Path(output).glob("*"))
            if path.is_file() and not path.is_symlink()
        ]
        return subprocess.run(
            [sys.executable, "-m", "twine", "check", *(str(path) for path in distributions)],
            cwd=ROOT,
            check=False,
        ).returncode


def _build_environment() -> dict[str, str]:
    """Pass the installed SCM-resolved version into a metadata-free source copy."""

    environment = os.environ.copy()
    with suppress(PackageNotFoundError):
        environment[SCM_VERSION_ENV] = package_version(PACKAGE_NAME)
    return environment


if __name__ == "__main__":
    raise SystemExit(main())
