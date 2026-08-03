"""Repository Markdown document graph construction."""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from mdrepo.config import ApplicationConfig
from mdrepo.models import Document, LinkKind, LinkOccurrence
from mdrepo.repository import RepositoryIdentity, parse_same_repository_url
from mdrepo.resolution import canonicalize_case, resolve_graph_document, resolve_local_target


@dataclass(frozen=True, slots=True)
class DocumentGraph:
    """Directed graph of Markdown documents linked from other Markdown documents."""

    edges: dict[Path, frozenset[Path]]
    roots: tuple[Path, ...]
    reachable: frozenset[Path]


def build_document_graph(
    *,
    root: Path,
    documents: dict[Path, Document],
    config: ApplicationConfig,
    identity: RepositoryIdentity | None,
) -> DocumentGraph:
    """Build local and same-repository web edges, then walk configured roots."""

    mutable_edges: dict[Path, set[Path]] = {path: set() for path in documents}
    for document in documents.values():
        for occurrence in document.links:
            if occurrence.kind is LinkKind.IMAGE:
                continue

            target_document = _link_document_target(
                root=root,
                document=document,
                occurrence=occurrence,
                documents=documents,
                config=config,
                identity=identity,
            )
            if target_document is not None:
                mutable_edges[document.path].add(target_document)

    roots = _resolve_roots(
        root=root,
        configured=config.orphans.roots,
        documents=documents,
    )
    frozen_edges = {
        path: frozenset(targets)
        for path, targets in sorted(
            mutable_edges.items(),
            key=lambda item: item[0].relative_to(root).as_posix(),
        )
    }
    reachable = _walk(edges=frozen_edges, roots=roots)
    return DocumentGraph(
        edges=frozen_edges,
        roots=roots,
        reachable=frozenset(reachable),
    )


def _link_document_target(
    *,
    root: Path,
    document: Document,
    occurrence: LinkOccurrence,
    documents: dict[Path, Document],
    config: ApplicationConfig,
    identity: RepositoryIdentity | None,
) -> Path | None:
    local = resolve_local_target(
        root=root,
        document=document,
        occurrence=occurrence,
        config=config.links,
    )
    if local is not None:
        return resolve_graph_document(
            root=root,
            resolution=local,
            documents=documents,
            config=config.orphans,
        )

    if identity is None:
        return None
    remote = parse_same_repository_url(target=occurrence.target, identity=identity)
    if remote is None:
        return None
    candidate = Path(os.path.abspath(os.path.join(root, remote.repository_path.as_posix())))
    canonical, exists, _ = canonicalize_case(root=root, candidate=candidate)
    if not exists or canonical is None:
        return None
    resolved = canonical.resolve()
    return resolved if resolved in documents else None


def _resolve_roots(
    *,
    root: Path,
    configured: list[str],
    documents: dict[Path, Document],
) -> tuple[Path, ...]:
    roots: list[Path] = []
    for configured_root in configured:
        candidate = Path(os.path.abspath(os.path.join(root, configured_root)))
        canonical, exists, _ = canonicalize_case(root=root, candidate=candidate)
        if exists and canonical is not None and canonical.resolve() in documents:
            roots.append(canonical.resolve())
    return tuple(dict.fromkeys(roots))


def _walk(
    *,
    edges: dict[Path, frozenset[Path]],
    roots: tuple[Path, ...],
) -> set[Path]:
    reachable: set[Path] = set()
    queue: deque[Path] = deque(roots)
    while queue:
        current = queue.popleft()
        if current in reachable:
            continue
        reachable.add(current)
        queue.extend(sorted(edges.get(current, ())))
    return reachable
