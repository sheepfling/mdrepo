"""Repository Markdown file discovery and CLI path selection."""

from __future__ import annotations

from pathlib import Path

from pathspec import GitIgnoreSpec

from mdrepo.config import ApplicationConfig

class FileDiscoveryError(RuntimeError):
    """Raised when requested repository inputs are invalid."""

def collect_project_markdown(*, root: Path, config: ApplicationConfig) -> tuple[Path, ...]:
    """Collect all configured Markdown files beneath the project root."""

    include_spec = GitIgnoreSpec.from_lines(config.include)
    exclude_spec = GitIgnoreSpec.from_lines(config.exclude)
    collected: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if exclude_spec.match_file(relative):
            continue
        if include_spec.match_file(relative):
            collected.append(path.resolve())
    return tuple(sorted(collected, key=lambda path: path.relative_to(root).as_posix()))

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

        selected.update(path for path in project_paths if path.is_relative_to(candidate))
    return tuple(sorted(selected, key=lambda path: path.relative_to(root).as_posix()))
