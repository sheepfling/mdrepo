"""Repository Markdown file discovery and CLI path selection."""

from __future__ import annotations

import stat
from pathlib import Path

from mdrepo.config import ApplicationConfig
from mdrepo.gitignore import parse_gitignore


class FileDiscoveryError(RuntimeError):
    """Raised when requested repository inputs are invalid."""


def collect_project_markdown(*, root: Path, config: ApplicationConfig) -> tuple[Path, ...]:
    """Collect all configured Markdown files beneath the project root."""

    include_spec = parse_gitignore(config.include, source="mdrepo include policy")
    exclude_spec = parse_gitignore(config.exclude, source="mdrepo exclude policy")
    collected: list[Path] = []
    try:
        for path in root.rglob("*"):
            if not _is_regular_file(path):
                continue
            relative = path.relative_to(root).as_posix()
            if exclude_spec.match_file(relative):
                continue
            if include_spec.match_file(relative):
                collected.append(path.resolve())
    except OSError as error:
        raise FileDiscoveryError(
            f"unable to inspect repository files under {root}: {error}"
        ) from error
    return tuple(
        sorted(collected, key=lambda candidate_path: candidate_path.relative_to(root).as_posix())
    )


def _is_regular_file(path: Path) -> bool:
    """Return whether a candidate is a non-symlink regular file."""

    try:
        if path.is_symlink():
            return False
        if not stat.S_ISREG(path.stat().st_mode):
            return False
        return path.is_file()
    except OSError as error:
        raise FileDiscoveryError(f"unable to inspect repository path {path}: {error}") from error


def select_requested_markdown(
    *,
    root: Path,
    requested_paths: list[str],
    project_paths: tuple[Path, ...],
) -> tuple[Path, ...]:
    """Resolve explicit files or directories against the project document set."""

    if not requested_paths:
        return project_paths

    selected: set[Path] = set()
    project_set = set(project_paths)
    for raw_path in requested_paths:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.is_symlink():
            raise FileDiscoveryError(f"input path must not be a symlink: {candidate}")
        candidate = candidate.resolve()
        if not candidate.exists():
            raise FileDiscoveryError(f"input path does not exist: {candidate}")
        if not candidate.is_relative_to(root):
            raise FileDiscoveryError(f"input path is outside the project root: {candidate}")

        if candidate.is_file():
            if candidate not in project_set:
                raise FileDiscoveryError(
                    f"input file is not selected by mdrepo include/exclude policy: {candidate}"
                )
            selected.add(candidate)
            continue

        selected.update(
            project_path for project_path in project_paths if project_path.is_relative_to(candidate)
        )
    return tuple(
        sorted(selected, key=lambda selected_path: selected_path.relative_to(root).as_posix())
    )
