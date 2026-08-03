"""Run the repository's CI checks locally and in hosted CI."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def ci_commands(
        python: str = sys.executable,
        *,
        fix: bool = False,
) -> tuple[tuple[str, ...], ...]:
    """Return the ordered, platform-independent commands used by CI."""

    ruff_check = (python, "-m", "ruff", "check")
    ruff_format = (python, "-m", "ruff", "format")
    rumdl = (python, "scripts/check_rumdl.py")
    mdrepo_fix = (python, "-m", "mdrepo", "fix", ".")

    python_paths = ("src", "scripts", "tests")
    commands: list[tuple[str, ...]] = [
        (python, "-m", "compileall", "-q", *python_paths),
    ]
    if fix:
        commands.extend(
            [
                (*ruff_check, "--fix", *python_paths),
                ruff_format + python_paths,
                (*rumdl, "--fix"),
                mdrepo_fix,
            ]
        )
    commands.extend(
        [
            ruff_check + python_paths,
            (python, "scripts/check_format.py"),
            (
                python,
                "-m",
                "pytest",
                "--cov=mdrepo",
                "--cov-report=term-missing",
            ),
            (python, "scripts/check_build.py"),
            (python, "scripts/check_pre_commit.py"),
            (python, "-m", "pyright", "--pythonpath", python),
            rumdl,
            (python, "-m", "pre_commit", "run", "--all-files"),
            (python, "-m", "mdrepo", "check", "."),
        ]
    )
    return tuple(commands)

def run_command(command: Sequence[str]) -> int:
    """Run one CI command from the repository root and return its exit code."""

    environment = os.environ.copy()
    source_path = str(ROOT / "src")
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        path for path in (source_path, existing_pythonpath) if path
    )
    python_path = Path(command[0])
    if python_path.is_absolute():
        existing_path = environment.get("PATH")
        environment["PATH"] = os.pathsep.join(
            path for path in (str(python_path.parent), existing_path) if path
        )
    environment["PRE_COMMIT_HOME"] = str(ROOT / ".pre-commit-cache")
    try:
        completed = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    except OSError as error:
        print(f"CI command could not start: {' '.join(command)}: {error}", file=sys.stderr)
        return 1
    return completed.returncode

def main(argv: Sequence[str] = ()) -> int:
    """Run each CI command in order, stopping at the first failure."""

    parser = argparse.ArgumentParser(
        description="Run the repository's checks in the same order as CI.",
        epilog=(
            "By default every check is read-only. With --fix, Ruff, rumdl, "
            "and mdrepo may update files."
        ),
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="allow formatting and lint tools to rewrite files",
    )
    args = parser.parse_args(argv)
    for command in ci_commands(fix=args.fix):
        print(f"$ {' '.join(command)}")
        return_code = run_command(command)
        if return_code:
            return return_code
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
