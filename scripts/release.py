"""Build and validate release distributions outside the hosting-provider workflow."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]


class ReleaseError(RuntimeError):
    """Raised when release metadata or artifacts are invalid."""


def project_version() -> str:
    """Read the package version from the authoritative project metadata."""

    with (ROOT / "pyproject.toml").open("rb") as stream:
        document: dict[str, Any] = tomllib.load(stream)
    project = document.get("project")
    if not isinstance(project, dict):
        raise ReleaseError("pyproject.toml does not define project.version")
    project_data = cast(dict[str, Any], project)
    version = project_data.get("version")
    if not isinstance(version, str):
        raise ReleaseError("pyproject.toml does not define project.version")
    return version


def verify_tag(tag: str | None) -> None:
    """Require a release tag to match the project version."""

    release_tag = tag or os.environ.get("RELEASE_TAG")
    if not release_tag:
        raise ReleaseError("RELEASE_TAG is required for a release build")
    if release_tag.removeprefix("v") != project_version():
        raise ReleaseError(
            f"release tag {release_tag!r} does not match project version {project_version()!r}"
        )


def build_release(*, output: Path, tag: str | None = None) -> tuple[Path, ...]:
    """Build sdist and wheel, validate them with twine, and return their paths."""

    verify_tag(tag)
    output.mkdir(parents=True, exist_ok=True)
    build_command = [
        sys.executable,
        "-m",
        "build",
        "--sdist",
        "--wheel",
        "--outdir",
        str(output),
    ]
    result = subprocess.run(build_command, cwd=ROOT, check=False)
    if result.returncode:
        raise ReleaseError(f"distribution build failed with status {result.returncode}")

    distributions = tuple(sorted(output.glob("*.whl"))) + tuple(sorted(output.glob("*.tar.gz")))
    if not distributions:
        raise ReleaseError(f"no distributions were produced in {output}")

    check_command = [sys.executable, "-m", "twine", "check", *(str(path) for path in distributions)]
    result = subprocess.run(check_command, cwd=ROOT, check=False)
    if result.returncode:
        raise ReleaseError(f"twine validation failed with status {result.returncode}")
    return distributions


def main(argv: tuple[str, ...] = ()) -> int:
    """Run one provider-neutral release operation."""

    parser = argparse.ArgumentParser(description="Build and validate mdrepo release artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Build and validate the release distributions.")
    build.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args(list(argv))

    try:
        if args.command == "build":
            build_release(output=args.output)
    except (OSError, ReleaseError) as error:
        print(f"release: error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(tuple(sys.argv[1:])))
