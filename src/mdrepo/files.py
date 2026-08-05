"""Repository Markdown file discovery and CLI path selection."""

from __future__ import annotations

from pathlib import Path

from mdrepo.config import ApplicationConfig
from mdrepo.gitignore import GitIgnoreEngine, GitIgnoreError, matches_gitignore, parse_gitignore


class FileDiscoveryError(RuntimeError):
    """Raised when requested repository inputs are invalid."""


def collect_project_markdown(*, root: Path, config: ApplicationConfig) -> tuple[Path, ...]:
    """Collect all configured Markdown files beneath the project root."""

    include_spec = parse_gitignore(config.include, source="mdrepo include policy")
    exclude_spec = parse_gitignore(config.exclude, source="mdrepo exclude policy")
    gitignore = GitIgnoreEngine(root)
    collected: list[Path] = []
    try:
        ignored = False if config.respect_gitignore else None
        for directory, _, filenames in gitignore.walk(ignored=ignored):
            for filename in filenames:
                path = directory / filename
                relative = path.relative_to(root).as_posix()
                if matches_gitignore(exclude_spec, relative, is_directory=False):
                    continue
                if matches_gitignore(include_spec, relative, is_directory=False):
                    collected.append(path.resolve())
    except (GitIgnoreError, OSError) as error:
        raise FileDiscoveryError(
            f"unable to inspect repository files under {root}: {error}"
        ) from error
    return tuple(
        sorted(collected, key=lambda candidate_path: candidate_path.relative_to(root).as_posix())
    )


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
