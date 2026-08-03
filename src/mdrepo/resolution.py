"""Portable local-link resolution and safe replacement generation."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import SplitResult, quote, unquote, urlsplit, urlunsplit

from mdrepo.config import OrphanConfig
from mdrepo.models import Document, LinkOccurrence

_WINDOWS_ABSOLUTE: Final[re.Pattern[str]] = re.compile(r"^(?:[A-Za-z]:[\\/]|\\{2})")

@dataclass(frozen=True, slots=True)
class LocalTargetResolution:
    """Filesystem interpretation of one local Markdown destination."""

    occurrence: LinkOccurrence
    parsed: SplitResult
    decoded_path: str
    has_backslashes: bool
    windows_absolute: bool
    root_relative: bool
    protocol_relative: bool
    file_uri: bool
    home_relative: bool
    outside_root: bool
    candidate_path: Path | None
    canonical_path: Path | None
    exists: bool
    case_mismatch: bool
    suggested_target: str | None

    @property
    def absolute(self) -> bool:
        """Return whether the destination is machine- or root-absolute."""

        return (
                self.windows_absolute
                or self.root_relative
                or self.protocol_relative
                or self.file_uri
                or self.home_relative
        )

def resolve_local_target(
        *,
        root: Path,
        document: Document,
        occurrence: LinkOccurrence,
) -> LocalTargetResolution | None:
    """Resolve a destination when it represents a local repository path."""

    target = occurrence.target.strip()
    if not target or target.startswith("#") or target.startswith("?"):
        return None

    decoded_whole = unquote(target)
    windows_absolute = bool(_WINDOWS_ABSOLUTE.match(decoded_whole))
    protocol_relative = target.startswith("//")
    home_relative = decoded_whole == "~" or decoded_whole.startswith(("~/", "~\\"))

    try:
        parsed = urlsplit(target)
    except ValueError:
        return None
    scheme = parsed.scheme.lower()
    file_uri = scheme == "file"
    if scheme and not windows_absolute and not file_uri:
        return None
    if parsed.netloc and not protocol_relative and not file_uri:
        return None

    decoded_path = unquote(parsed.path)
    has_backslashes = "\\" in decoded_path
    normalized_path = decoded_path.replace("\\", "/")
    root_relative = normalized_path.startswith("/") and not protocol_relative

    candidate_path: Path | None = None
    canonical_path: Path | None = None
    exists = False
    case_mismatch = False
    outside_root = False

    if (
            not windows_absolute
            and not protocol_relative
            and not file_uri
            and not home_relative
            and normalized_path
    ):
        base = root if root_relative else document.path.parent
        path_text = normalized_path.lstrip("/") if root_relative else normalized_path
        candidate_path = Path(os.path.abspath(os.path.join(base, path_text)))
        if not candidate_path.is_relative_to(root):
            outside_root = True
        else:
            canonical_path, exists, case_mismatch = canonicalize_case(
                root=root,
                candidate=candidate_path,
            )
            resolved_candidate = (canonical_path or candidate_path).resolve(strict=False)
            if not resolved_candidate.is_relative_to(root):
                outside_root = True

    suggested_target: str | None = None
    if candidate_path is not None and not outside_root:
        target_path = canonical_path or candidate_path
        suggested_target = make_relative_target(
            source=document.path,
            target=target_path,
            query=parsed.query,
            fragment=parsed.fragment,
        )

    return LocalTargetResolution(
        occurrence=occurrence,
        parsed=parsed,
        decoded_path=decoded_path,
        has_backslashes=has_backslashes,
        windows_absolute=windows_absolute,
        root_relative=root_relative,
        protocol_relative=protocol_relative,
        file_uri=file_uri,
        home_relative=home_relative,
        outside_root=outside_root,
        candidate_path=candidate_path,
        canonical_path=canonical_path,
        exists=exists,
        case_mismatch=case_mismatch,
        suggested_target=suggested_target,
    )

def canonicalize_case(
        *,
        root: Path,
        candidate: Path,
) -> tuple[Path | None, bool, bool]:
    """Find the exact on-disk path spelling independent of host case sensitivity."""

    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return None, False, False

    current = root
    mismatch = False
    for part in relative.parts:
        if not current.is_dir():
            return None, False, mismatch
        try:
            children = tuple(current.iterdir())
        except OSError:
            return None, False, mismatch

        exact = next((child for child in children if child.name == part), None)
        if exact is not None:
            current = exact
            continue

        folded = [child for child in children if child.name.casefold() == part.casefold()]
        if len(folded) != 1:
            return None, False, mismatch
        current = folded[0]
        mismatch = True
    return current, current.exists(), mismatch

def make_relative_target(
        *,
        source: Path,
        target: Path,
        query: str = "",
        fragment: str = "",
) -> str:
    """Create a POSIX, percent-encoded destination relative to a source document."""

    relative = os.path.relpath(target, start=source.parent).replace(os.sep, "/")
    encoded = quote(relative, safe="/.-_~")
    return urlunsplit(("", "", encoded, query, fragment))

def resolve_graph_document(
        *,
        root: Path,
        resolution: LocalTargetResolution,
        documents: dict[Path, Document],
        config: OrphanConfig,
) -> Path | None:
    """Resolve local paths, extensionless routes, and directory indexes to Markdown documents."""

    if resolution.outside_root or (resolution.absolute and resolution.candidate_path is None):
        return None
    base_candidate = resolution.canonical_path or resolution.candidate_path
    if base_candidate is None:
        return None

    candidate = _document_candidate(
        root=root,
        candidate=base_candidate,
        documents=documents,
    )
    if candidate is not None:
        return candidate

    if base_candidate.is_dir():
        for index_name in config.directory_indexes:
            indexed = _document_candidate(
                root=root,
                candidate=base_candidate / index_name,
                documents=documents,
            )
            if indexed is not None:
                return indexed

    if config.extensionless_links and not base_candidate.suffix:
        for extension in config.markdown_extensions:
            extended = _document_candidate(
                root=root,
                candidate=base_candidate.with_suffix(extension),
                documents=documents,
            )
            if extended is not None:
                return extended
    return None

def _document_candidate(
        *,
        root: Path,
        candidate: Path,
        documents: dict[Path, Document],
) -> Path | None:
    canonical, exists, _ = canonicalize_case(root=root, candidate=candidate)
    if not exists or canonical is None:
        return None
    resolved = canonical.resolve()
    return resolved if resolved in documents else None
