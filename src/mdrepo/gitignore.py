"""Compatibility API and mdrepo durability policy backed by gitignore-walk."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from gitignore_walk import GitIgnoreDecision as GitIgnoreDecision
from gitignore_walk import GitIgnoreError as GitIgnoreError
from gitignore_walk import GitIgnorePolicy as _GitIgnorePolicy
from gitignore_walk import GitIgnoreSpec
from gitignore_walk import GitIgnoreWalker as _GitIgnoreWalker
from gitignore_walk import matches_gitignore as matches_gitignore
from gitignore_walk import parse_gitignore as parse_gitignore


class GitIgnorePolicy:
    """Adapt the library policy while preserving mdrepo's tuple batch results.

    Empty initial exclusions preserve mdrepo's historical baseline. Portable library scope
    includes conventional global excludes, repository info/exclude, and repository ignore files.
    """

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        initial_excludes: Sequence[str] = (),
    ) -> None:
        self.backend = _GitIgnorePolicy(root, initial_excludes=initial_excludes)
        self.root = self.backend.root

    def is_ignored(self, target: str | os.PathLike[str]) -> bool:
        """Return whether the target is ignored."""
        return self.backend.is_ignored(target)

    def explain(self, target: str | os.PathLike[str]) -> GitIgnoreDecision:
        """Explain the effective ignore decision and its source."""
        return self.backend.explain(target)

    def is_ignored_many(self, targets: Iterable[str | os.PathLike[str]]) -> tuple[bool, ...]:
        """Return decisions in input order using one fresh policy snapshot."""
        return tuple(self.backend.is_ignored_many(targets))

    def resolve_target(self, target: str | os.PathLike[str]) -> Path:
        """Resolve a target within the policy root."""
        return self.backend.resolve_target(target)


class GitIgnoreWalker:
    """Adapt mdrepo's ignored selector to gitignore-walk's selection API."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        policy: GitIgnorePolicy | None = None,
        initial_excludes: Sequence[str] = (),
    ) -> None:
        self.policy = policy or GitIgnorePolicy(root, initial_excludes=initial_excludes)
        self._walker = _GitIgnoreWalker(root, policy=self.policy.backend)
        self.root = self._walker.root

    def walk(
        self,
        top: str | os.PathLike[str] | None = None,
        *,
        topdown: bool = True,
        onerror: Callable[[OSError], object] | None = None,
        follow_links: bool = False,
        ignored: bool | None = None,
    ) -> Iterator[tuple[Path, list[str], list[str]]]:
        """Walk safe entries; None selects all, True ignored, and False included."""
        if follow_links:
            raise ValueError("GitIgnoreWalker.walk does not follow symlinks")
        yield from self._walker.walk(
            top,
            topdown=topdown,
            onerror=onerror,
            selection="all" if ignored is None else "ignored" if ignored else "included",
        )

    def iter_files(
        self,
        top: str | os.PathLike[str] | None = None,
        *,
        topdown: bool = True,
        onerror: Callable[[OSError], object] | None = None,
        follow_links: bool = False,
        ignored: bool | None = None,
    ) -> Iterator[Path]:
        """Yield safe file paths with the same options as walk()."""
        for directory, _, filenames in self.walk(
            top,
            topdown=topdown,
            onerror=onerror,
            follow_links=follow_links,
            ignored=ignored,
        ):
            yield from (directory / filename for filename in filenames)


@dataclass(frozen=True, slots=True)
class TargetDurability:
    """Ignore and mdrepo policies that exclude one existing local target."""

    gitignored: bool
    mdrepo_excluded: bool

    @property
    def excluded(self) -> bool:
        """Return whether the target is excluded by any repository policy."""

        return self.gitignored or self.mdrepo_excluded


@dataclass(frozen=True, slots=True)
class TargetDurabilityPolicy:
    """Classify existing targets against portable ignore and mdrepo policies."""

    root: Path
    mdrepo_exclude: GitIgnoreSpec
    gitignore: GitIgnorePolicy

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
            mdrepo_exclude=parse_gitignore(exclude_patterns, source="mdrepo exclude policy"),
            gitignore=GitIgnorePolicy(root),
        )

    def classify(self, target: Path) -> TargetDurability:
        """Return the exclusion status for one existing repository target."""

        relative = target.relative_to(self.root).as_posix()
        return TargetDurability(
            gitignored=self.gitignore.is_ignored(target),
            mdrepo_excluded=matches_gitignore(
                self.mdrepo_exclude,
                relative,
                is_directory=target.is_dir(),
            ),
        )


def is_gitignored(
    root: str | os.PathLike[str] | Path,
    target: str | os.PathLike[str] | Path,
) -> bool:
    """Return whether ``target`` is ignored by the portable policy rooted at ``root``.

    ``root`` and ``target`` may be strings or path-like objects. Relative targets are interpreted
    relative to ``root``. The target must be inside the root; passing an outside path raises
    :class:`ValueError` rather than silently reporting a false result. Ignore-file read and parse
    failures raise :class:`GitIgnoreError`.
    """

    return GitIgnorePolicy(root).is_ignored(target)
