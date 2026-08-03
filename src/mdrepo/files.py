"""Repository Markdown file discovery and CLI path selection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pathspec import GitIgnoreSpec

from mdrepo.config import ApplicationConfig


class FileDiscoveryError(RuntimeError):
    """Raised when requested repository inputs are invalid."""


@dataclass(frozen=True, slots=True)
class TargetDurability:
    """Repository policies that exclude one existing local target."""

    gitignored: bool
    mdrepo_excluded: bool

    @property
    def excluded(self) -> bool:
        """Return whether the target is excluded by any repository policy."""

        return self.gitignored or self.mdrepo_excluded


@dataclass(frozen=True, slots=True)
class TargetDurabilityPolicy:
    """Classify existing targets against repository-owned exclusion policies."""

    root: Path
    mdrepo_exclude: GitIgnoreSpec

    @classmethod
    def from_repository(
        cls,
        *,
        root: Path,
        exclude_patterns: Sequence[str],
    ) -> TargetDurabilityPolicy:
        """Load mdrepo exclusions and the repository's applicable ``.gitignore`` files."""

        return cls(
            root=root,
            mdrepo_exclude=GitIgnoreSpec.from_lines(exclude_patterns),
        )

    def classify(self, target: Path) -> TargetDurability:
        """Return the exclusion status for one existing repository target."""

        relative = target.relative_to(self.root).as_posix()
        gitignored = False
        for ignore_root in _ancestor_directories(root=self.root, target=target):
            spec = _load_gitignore(ignore_root / ".gitignore")
            if spec is None:
                continue
            ignored = _last_gitignore_match(spec, target.relative_to(ignore_root).as_posix())
            if ignored is not None:
                gitignored = ignored
        return TargetDurability(
            gitignored=gitignored,
            mdrepo_excluded=_last_gitignore_match(
                self.mdrepo_exclude,
                relative,
            )
            is True,
        )


def _ancestor_directories(*, root: Path, target: Path) -> tuple[Path, ...]:
    """Return target-parent directories from the repository root outward."""

    directories: list[Path] = []
    current = target.parent
    while current.is_relative_to(root):
        directories.append(current)
        if current == root:
            break
        current = current.parent
    directories.reverse()
    return tuple(directories)


@lru_cache(maxsize=256)
def _load_gitignore(path: Path) -> GitIgnoreSpec | None:
    """Load one non-symlink ``.gitignore`` file, if present."""

    if not path.is_file() or path.is_symlink():
        return None
    try:
        return GitIgnoreSpec.from_lines(path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeError) as error:
        raise FileDiscoveryError(
            f"unable to read repository .gitignore: {path}: {error}"
        ) from error


def _last_gitignore_match(spec: GitIgnoreSpec, relative: str) -> bool | None:
    """Return the final include decision for one path within one ignore file."""

    decision: bool | None = None
    for pattern in spec.patterns:
        if pattern.match_file(relative) or pattern.match_file(f"{relative}/"):
            decision = pattern.include
    return decision


def collect_project_markdown(*, root: Path, config: ApplicationConfig) -> tuple[Path, ...]:
    """Collect all configured Markdown files beneath the project root."""

    include_spec = GitIgnoreSpec.from_lines(config.include)
    exclude_spec = GitIgnoreSpec.from_lines(config.exclude)
    collected: list[Path] = []
    for path in root.rglob("*"):
        if not _is_regular_file(path):
            continue
        relative = path.relative_to(root).as_posix()
        if exclude_spec.match_file(relative):
            continue
        if include_spec.match_file(relative):
            collected.append(path.resolve())
    return tuple(
        sorted(collected, key=lambda candidate_path: candidate_path.relative_to(root).as_posix())
    )


def _is_regular_file(path: Path) -> bool:
    """Return whether a candidate is a non-symlink regular file."""

    return path.is_file() and not path.is_symlink()


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
