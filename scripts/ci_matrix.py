"""Run the full local CI gate across installed supported Python versions."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.ci import ROOT, run_command

SUPPORTED_VERSIONS = tuple(f"3.{minor}" for minor in range(10, 16))


def find_interpreter(version: str) -> tuple[str, ...] | None:
    """Find an installed interpreter using its versioned command or Windows launcher."""

    if f"{sys.version_info.major}.{sys.version_info.minor}" == version:
        return (sys.executable,)
    executable = shutil.which(f"python{version}")
    if executable is not None and _supports_version((executable,), version):
        return (executable,)
    if sys.platform == "win32":
        launcher = shutil.which("py")
        command = (launcher, f"-{version}") if launcher is not None else ()
        if command and _supports_version(command, version):
            return command
    return None


def _supports_version(command: tuple[str, ...], version: str) -> bool:
    """Confirm an interpreter command selects the requested installed Python version."""

    environment = os.environ.copy()
    environment.pop("PYLAUNCHER_ALLOW_INSTALL", None)
    environment.pop("PYLAUNCHER_ALWAYS_INSTALL", None)
    try:
        result = subprocess.run(
            [
                *command,
                "-c",
                "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
            ],
            cwd=ROOT,
            capture_output=True,
            check=False,
            env=environment,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip() == version


def environment_python(version: str) -> Path:
    """Return the platform-specific Python executable in a version's local venv."""

    environment = ROOT / f".venv-ci-{version}"
    executable = "python.exe" if sys.platform == "win32" else "python"
    scripts_directory = "Scripts" if sys.platform == "win32" else "bin"
    return environment / scripts_directory / executable


def _run_version(version: str, interpreter: tuple[str, ...], *, fix: bool) -> int:
    """Create or refresh one isolated environment and run its full CI gate."""

    python = environment_python(version)
    environment = python.parents[1]
    if not python.exists():
        result = run_command((*interpreter, "-m", "venv", str(environment)))
        if result:
            return result
    try:
        version_check = subprocess.run(
            [
                str(python),
                "-c",
                "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
            ],
            cwd=ROOT,
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as error:
        print(f"Could not run Python {version} from {python}: {error}", file=sys.stderr)
        return 1
    if version_check.returncode or version_check.stdout.strip() != version:
        actual = version_check.stdout.strip() or "unavailable"
        print(
            f"Expected Python {version} in {environment}; found {actual}.",
            file=sys.stderr,
        )
        return version_check.returncode or 1

    install = run_command(
        (
            str(python),
            "-m",
            "pip",
            "install",
            "-e",
            ".[dev]",
        )
    )
    if install:
        return install

    ci_command = (str(python), "-m", "scripts.ci")
    if fix:
        ci_command += ("--fix",)
    return run_command(ci_command)


def main(argv: tuple[str, ...] = ()) -> int:
    """Run CI for every supported interpreter found on this machine."""

    parser = argparse.ArgumentParser(
        description=(
            "Create isolated environments and run the full CI gate for each installed "
            "Python version from 3.10 through 3.15."
        )
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="allow formatting and lint tools to rewrite files",
    )
    args = parser.parse_args(argv)

    available = [(version, find_interpreter(version)) for version in SUPPORTED_VERSIONS]
    found = [(version, command) for version, command in available if command is not None]
    missing = [version for version, command in available if command is None]
    for version in missing:
        print(f"Skipping Python {version}: interpreter not found.", file=sys.stderr)
    if not found:
        print("No supported Python interpreter was found.", file=sys.stderr)
        return 1

    for version, command in found:
        assert command is not None
        print(f"=== Python {version}: install development dependencies ===", flush=True)
        result = _run_version(version, command, fix=args.fix)
        if result:
            print(f"Local CI failed on Python {version} with exit code {result}.", file=sys.stderr)
            return result
        print(f"=== Python {version}: all CI checks passed ===", flush=True)

    if missing:
        print(f"Local CI passed on {len(found)} installed version(s); skipped {len(missing)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(tuple(sys.argv[1:])))
