"""Repository collection, parsing, rule execution, and exception application."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from mdrepo.config import LoadedConfig
from mdrepo.exceptions import apply_exceptions
from mdrepo.files import collect_project_markdown, select_requested_markdown
from mdrepo.graph import DocumentGraph, build_document_graph
from mdrepo.markdown import MarkdownParser
from mdrepo.models import Diagnostic, Document
from mdrepo.repository import RepositoryIdentity, discover_repository_identity
from mdrepo.resolution import resolve_local_target
from mdrepo.rules import (
    BUILTIN_RULES,
    RULES_BY_ID,
    PolicyLink,
    RuleContext,
    configured_severity,
    rule_enabled,
)


class EngineError(RuntimeError):
    """Raised when repository files cannot be read or checked safely."""
####




@dataclass(frozen=True, slots=True)
class RunResult:
    """Complete repository run result."""

    root: Path
    documents: dict[Path, Document]
    selected_documents: tuple[Document, ...]
    identity: RepositoryIdentity | None
    graph: DocumentGraph | None
    diagnostics: tuple[Diagnostic, ...]
    suppressed: tuple[Diagnostic, ...]
####




def run_repository(
    *,
    loaded_config: LoadedConfig,
    requested_paths: list[str],
    force_graph: bool = False,
    today: date | None = None,
) -> RunResult:
    """Parse the repository and evaluate every enabled focused rule."""

    root = loaded_config.root
    project_paths = collect_project_markdown(root=root, config=loaded_config.model)
    selected_paths = select_requested_markdown(
        root=root,
        requested_paths=requested_paths,
        project_paths=project_paths,
    )

    parser = MarkdownParser()
    documents: dict[Path, Document] = {}
    for path in project_paths:
        try:
            text = path.read_bytes().decode(loaded_config.model.encoding)
        except (OSError, UnicodeError) as error:
            raise EngineError(f"unable to read Markdown document {path}: {error}") from error
        ####
        document = parser.parse(path=path, root=root, text=text)
        documents[document.path] = document
    ####

    selected_documents = tuple(documents[path] for path in selected_paths)
    identity = discover_repository_identity(
        root=root,
        config=loaded_config.model.repository,
    )

    policy_links: list[PolicyLink] = []
    for document in selected_documents:
        for occurrence in document.policy_occurrences:
            policy_links.append(
                PolicyLink(
                    document=document,
                    occurrence=occurrence,
                    local=resolve_local_target(
                        root=root,
                        document=document,
                        occurrence=occurrence,
                        config=loaded_config.model.links,
                    ),
                )
            )
        ####
    ####

    graph: DocumentGraph | None = None
    if force_graph or loaded_config.model.orphans.enabled:
        graph = build_document_graph(
            root=root,
            documents=documents,
            config=loaded_config.model,
            identity=identity,
        )
    ####

    context = RuleContext(
        root=root,
        config=loaded_config.model,
        documents=documents,
        selected_documents=selected_documents,
        policy_links=tuple(policy_links),
        identity=identity,
        graph=graph,
    )
    raw_diagnostics: list[Diagnostic] = []
    for rule in BUILTIN_RULES:
        if not rule_enabled(config=loaded_config.model, rule_id=rule.metadata.rule_id):
            continue
        ####
        raw_diagnostics.extend(rule.check(context))
    ####

    configured = tuple(
        diagnostic.with_severity(
            configured_severity(config=loaded_config.model, diagnostic=diagnostic)
        )
        for diagnostic in _deduplicate(raw_diagnostics)
    )
    exception_result = apply_exceptions(
        diagnostics=configured,
        config=loaded_config.model,
        today=today,
        report_unused=selected_paths == project_paths,
        enabled_rules={
            rule_id
            for rule_id in RULES_BY_ID
            if rule_enabled(config=loaded_config.model, rule_id=rule_id)
        },
    )

    health = tuple(
        diagnostic.with_severity(
            configured_severity(config=loaded_config.model, diagnostic=diagnostic)
        )
        for diagnostic in exception_result.health
        if rule_enabled(config=loaded_config.model, rule_id=diagnostic.rule_id)
    )
    visible = _sort_diagnostics((*exception_result.visible, *health))
    suppressed = _sort_diagnostics(exception_result.suppressed)
    return RunResult(
        root=root,
        documents=documents,
        selected_documents=selected_documents,
        identity=identity,
        graph=graph,
        diagnostics=visible,
        suppressed=suppressed,
    )
####




def _deduplicate(diagnostics: list[Diagnostic]) -> tuple[Diagnostic, ...]:
    unique: dict[tuple[object, ...], Diagnostic] = {}
    for diagnostic in diagnostics:
        key = (
            diagnostic.rule_id,
            diagnostic.path,
            diagnostic.line,
            diagnostic.column,
            diagnostic.target,
            diagnostic.message,
        )
        unique.setdefault(key, diagnostic)
    ####
    return tuple(unique.values())
####




def _sort_diagnostics(diagnostics: tuple[Diagnostic, ...]) -> tuple[Diagnostic, ...]:
    return tuple(
        sorted(
            diagnostics,
            key=lambda diagnostic: (
                diagnostic.path.as_posix() if diagnostic.path is not None else "",
                diagnostic.line or 0,
                diagnostic.column or 0,
                diagnostic.rule_id,
                diagnostic.message,
            ),
        )
    )
####


