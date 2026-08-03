"""Repository Git-ignore interpretation for durable local-link checks."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pathspec import GitIgnoreSpec


class GitIgnoreError(RuntimeError):
    """Raised when a repository ignore file cannot be interpreted safely."""


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
        """Load mdrepo exclusions for one repository."""

        return cls(
            root=root,
            mdrepo_exclude=GitIgnoreSpec.from_lines(exclude_patterns),
        )

    def classify(self, target: Path) -> TargetDurability:
        """Return the exclusion status for one existing repository target."""

        relative = target.relative_to(self.root).as_posix()
        return TargetDurability(
            gitignored=_is_gitignored(root=self.root, target=target),
            mdrepo_excluded=_last_gitignore_match(self.mdrepo_exclude, relative) is True,
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


def _is_gitignored(*, root: Path, target: Path) -> bool:
    """Apply Git's parent-directory traversal rule before file negations."""

    directories = _ancestor_directories(root=root, target=target)
    ignored = False
    for index, directory in enumerate(directories):
        if directory == root:
            continue
        if ignored:
            # Git cannot traverse an ignored parent to discover a later negation.
            continue
        decision = _gitignore_decision(roots=directories[:index], path=directory)
        if decision is not None:
            ignored = decision

    if ignored:
        return True
    decision = _gitignore_decision(roots=directories, path=target)
    return decision is True


def _gitignore_decision(*, roots: Sequence[Path], path: Path) -> bool | None:
    """Return the last matching decision from applicable ignore files."""

    decision: bool | None = None
    for ignore_root in roots:
        spec = _load_gitignore(ignore_root / ".gitignore")
        if spec is None:
            continue
        relative = path.relative_to(ignore_root).as_posix()
        matched = _last_gitignore_match(spec, relative)
        if matched is not None:
            decision = matched
    return decision


def _load_gitignore(path: Path) -> GitIgnoreSpec | None:
    """Load one non-symlink ``.gitignore`` file, if present."""

    if not path.is_file() or path.is_symlink():
        return None
    try:
        return GitIgnoreSpec.from_lines(path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeError) as error:
        raise GitIgnoreError(f"unable to read repository .gitignore: {path}: {error}") from error


def _last_gitignore_match(spec: GitIgnoreSpec, relative: str) -> bool | None:
    """Return the final include decision for one path within one ignore file."""

    decision: bool | None = None
    for pattern in spec.patterns:
        if pattern.match_file(relative) or pattern.match_file(f"{relative}/"):
            decision = pattern.include
    return decision
