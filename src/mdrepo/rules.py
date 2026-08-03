"""Focused built-in repository policy rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from mdrepo.config import ApplicationConfig
from mdrepo.graph import DocumentGraph
from mdrepo.models import (
    Diagnostic,
    Document,
    Fix,
    LinkKind,
    LinkOccurrence,
    RuleMetadata,
    Severity,
)
from mdrepo.repository import RepositoryIdentity, parse_same_repository_url
from mdrepo.resolution import (
    LocalTargetResolution,
    canonicalize_case,
    make_repository_target,
)

RULE_METADATA: tuple[RuleMetadata, ...] = (
    RuleMetadata(
        rule_id="MDR001",
        name="non-posix-local-link",
        description="Local Markdown destinations must use POSIX forward slashes.",
        default_severity=Severity.ERROR,
        fixable=True,
    ),
    RuleMetadata(
        rule_id="MDR002",
        name="absolute-local-link",
        description="Machine-, protocol-, and repository-root-absolute destinations are forbidden.",
        default_severity=Severity.ERROR,
        fixable=True,
    ),
    RuleMetadata(
        rule_id="MDR003",
        name="link-escapes-repository",
        description="A local destination must remain inside the configured repository root.",
        default_severity=Severity.ERROR,
        fixable=False,
    ),
    RuleMetadata(
        rule_id="MDR004",
        name="missing-local-target",
        description="An optional standalone check for local destinations that do not exist.",
        default_severity=Severity.ERROR,
        fixable=False,
    ),
    RuleMetadata(
        rule_id="MDR005",
        name="local-target-case",
        description="Local path spelling must match on-disk case for cross-platform builds.",
        default_severity=Severity.ERROR,
        fixable=True,
    ),
    RuleMetadata(
        rule_id="MDR006",
        name="same-repository-web-link",
        description="Mutable web links back into this repository should be relative links.",
        default_severity=Severity.ERROR,
        fixable=True,
    ),
    RuleMetadata(
        rule_id="MDR100",
        name="missing-document-root",
        description="Orphan checking requires at least one existing configured graph root.",
        default_severity=Severity.ERROR,
        fixable=False,
    ),
    RuleMetadata(
        rule_id="MDR101",
        name="orphan-document",
        description="Markdown documents should be reachable from a configured documentation root.",
        default_severity=Severity.ERROR,
        fixable=False,
    ),
    RuleMetadata(
        rule_id="MDR201",
        name="expired-exception",
        description="Structured exceptions should not remain active past their expiry date.",
        default_severity=Severity.WARNING,
        fixable=False,
    ),
    RuleMetadata(
        rule_id="MDR202",
        name="unused-exception",
        description=(
            "Structured exceptions should be removed after their matching issue disappears."
        ),
        default_severity=Severity.WARNING,
        fixable=False,
    ),
)
RULES_BY_ID: dict[str, RuleMetadata] = {metadata.rule_id: metadata for metadata in RULE_METADATA}


@dataclass(frozen=True, slots=True)
class PolicyLink:
    """One editable policy destination with its local interpretation, when applicable."""

    document: Document
    occurrence: LinkOccurrence
    local: LocalTargetResolution | None


@dataclass(frozen=True, slots=True)
class RuleContext:
    """Read-only data supplied to every built-in rule."""

    root: Path
    config: ApplicationConfig
    documents: dict[Path, Document]
    selected_documents: tuple[Document, ...]
    policy_links: tuple[PolicyLink, ...]
    identity: RepositoryIdentity | None
    graph: DocumentGraph | None


class Rule(Protocol):
    """Small future-compatible seam for repository rules."""

    metadata: RuleMetadata

    def check(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        """Evaluate this rule for one repository context."""

        ...


class NonPosixLocalLinkRule:
    """MDR001 implementation."""

    metadata = RULES_BY_ID["MDR001"]

    def check(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if not context.config.links.require_posix:
            return ()
        diagnostics: list[Diagnostic] = []
        for link in context.policy_links:
            if link.local is None or not link.local.has_backslashes:
                continue
            diagnostics.append(
                _link_diagnostic(
                    metadata=self.metadata,
                    link=link,
                    message="local destination uses backslashes instead of POSIX '/' separators",
                    replacement=link.local.suggested_target,
                    fix_description="normalize the local destination to a POSIX relative path",
                )
            )
        return tuple(diagnostics)


class AbsoluteLocalLinkRule:
    """MDR002 implementation."""

    metadata = RULES_BY_ID["MDR002"]

    def check(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        diagnostics: list[Diagnostic] = []
        for link in context.policy_links:
            local = link.local
            if local is None or not local.absolute:
                continue
            if local.root_relative and context.config.links.allow_root_relative:
                continue

            if local.protocol_relative:
                message = "protocol-relative URL is neither fully qualified nor repository-relative"
            elif local.file_uri:
                message = "file:// destination is machine-local and not repository-portable"
            elif local.windows_absolute:
                message = "Windows absolute destination is machine-local and not portable"
            elif local.home_relative:
                message = "home-relative destination is machine-local and not portable"
            else:
                message = "repository-root-absolute destination should be relative to this document"
            replacement = local.suggested_target if local.root_relative and local.exists else None
            diagnostics.append(
                _link_diagnostic(
                    metadata=self.metadata,
                    link=link,
                    message=message,
                    replacement=replacement,
                    fix_description=(
                        "replace the repository-root path with a document-relative path"
                    ),
                )
            )
        return tuple(diagnostics)


class RepositoryEscapeRule:
    """MDR003 implementation."""

    metadata = RULES_BY_ID["MDR003"]

    def check(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.config.links.allow_outside_root:
            return ()
        return tuple(
            _link_diagnostic(
                metadata=self.metadata,
                link=link,
                message="local destination resolves outside the repository root",
            )
            for link in context.policy_links
            if link.local is not None and link.local.outside_root
        )


class MissingLocalTargetRule:
    """MDR004 implementation, disabled by default because rumdl already covers this area."""

    metadata = RULES_BY_ID["MDR004"]

    def check(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if not context.config.links.check_missing_targets:
            return ()

        diagnostics: list[Diagnostic] = []
        for link in context.policy_links:
            local = link.local
            if local is None or local.candidate_path is None or local.outside_root:
                continue
            if local.absolute and not (
                local.root_relative and context.config.links.allow_root_relative
            ):
                continue
            if local.exists:
                continue
            noun = "image" if link.occurrence.kind is LinkKind.IMAGE else "link"
            diagnostics.append(
                _link_diagnostic(
                    metadata=self.metadata,
                    link=link,
                    message=f"local {noun} target does not exist: {local.decoded_path}",
                )
            )
        return tuple(diagnostics)


class LocalTargetCaseRule:
    """MDR005 implementation."""

    metadata = RULES_BY_ID["MDR005"]

    def check(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if not context.config.links.check_case:
            return ()

        diagnostics: list[Diagnostic] = []
        for link in context.policy_links:
            local = link.local
            if local is None or not local.case_mismatch or local.canonical_path is None:
                continue
            canonical = local.canonical_path.relative_to(context.root).as_posix()
            diagnostics.append(
                _link_diagnostic(
                    metadata=self.metadata,
                    link=link,
                    message=f"local target case differs from the filesystem: {canonical}",
                    replacement=local.suggested_target,
                    fix_description="rewrite the destination with exact on-disk path case",
                )
            )
        return tuple(diagnostics)


class SameRepositoryWebLinkRule:
    """MDR006 implementation."""

    metadata = RULES_BY_ID["MDR006"]

    def check(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if context.identity is None:
            return ()

        diagnostics: list[Diagnostic] = []
        for link in context.policy_links:
            remote = parse_same_repository_url(
                target=link.occurrence.target,
                identity=context.identity,
            )
            if remote is None or remote.query or remote.line_fragment:
                continue

            target_path, replacement = make_repository_target(
                root=context.root,
                source=link.document.path,
                repository_path=remote.repository_path,
                fragment=remote.fragment,
            )
            canonical, exists, _ = canonicalize_case(root=context.root, candidate=target_path)
            if context.config.repository.require_existing_target and not exists:
                continue
            if canonical is not None:
                _, replacement = make_repository_target(
                    root=context.root,
                    source=link.document.path,
                    repository_path=PurePosixPath(canonical.relative_to(context.root).as_posix()),
                    fragment=remote.fragment,
                )

            diagnostics.append(
                _link_diagnostic(
                    metadata=self.metadata,
                    link=link,
                    message=(
                        f"web URL points back into this repository at mutable ref {remote.ref!r}; "
                        "use a portable relative destination"
                    ),
                    replacement=replacement if exists else None,
                    fix_description="replace the provider-specific web URL with a relative path",
                )
            )
        return tuple(diagnostics)


class MissingGraphRootRule:
    """MDR100 implementation."""

    metadata = RULES_BY_ID["MDR100"]

    def check(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if not context.config.orphans.enabled or context.graph is None or context.graph.roots:
            return ()
        return (
            Diagnostic(
                rule_id=self.metadata.rule_id,
                message="orphan checking is enabled, but no configured documentation root exists",
                severity=self.metadata.default_severity,
                hint=f"Configured roots: {', '.join(context.config.orphans.roots)}",
            ),
        )


class OrphanDocumentRule:
    """MDR101 implementation."""

    metadata = RULES_BY_ID["MDR101"]

    def check(self, context: RuleContext) -> tuple[Diagnostic, ...]:
        if not context.config.orphans.enabled or context.graph is None or not context.graph.roots:
            return ()

        diagnostics: list[Diagnostic] = []
        for document in sorted(
            context.documents.values(),
            key=lambda item: item.relative_path.as_posix(),
        ):
            if document.path in context.graph.reachable:
                continue
            diagnostics.append(
                Diagnostic(
                    rule_id=self.metadata.rule_id,
                    message="Markdown document is unreachable from every configured graph root",
                    severity=self.metadata.default_severity,
                    path=document.relative_path,
                    line=1,
                    column=1,
                    hint="Link the document into the graph or add a narrow structured exception.",
                )
            )
        return tuple(diagnostics)


BUILTIN_RULES: tuple[Rule, ...] = (
    NonPosixLocalLinkRule(),
    AbsoluteLocalLinkRule(),
    RepositoryEscapeRule(),
    MissingLocalTargetRule(),
    LocalTargetCaseRule(),
    SameRepositoryWebLinkRule(),
    MissingGraphRootRule(),
    OrphanDocumentRule(),
)


def rule_enabled(*, config: ApplicationConfig, rule_id: str) -> bool:
    """Apply stable select/ignore semantics to one rule ID."""

    selected = set(config.rules.select)
    ignored = set(config.rules.ignore)
    if selected and rule_id not in selected:
        return False
    return rule_id not in ignored


def configured_severity(*, config: ApplicationConfig, diagnostic: Diagnostic) -> Severity:
    """Return a rule-specific severity override or the emitted default."""

    return config.rules.severity.get(diagnostic.rule_id, diagnostic.severity)


def _link_diagnostic(
    *,
    metadata: RuleMetadata,
    link: PolicyLink,
    message: str,
    replacement: str | None = None,
    fix_description: str = "",
) -> Diagnostic:
    fix: Fix | None = None
    span = link.occurrence.span
    if replacement is not None and span is not None and replacement != link.occurrence.raw_target:
        fix = Fix(
            path=link.document.path,
            span=span,
            expected=link.occurrence.raw_target,
            replacement=replacement,
            description=fix_description,
        )
    return Diagnostic(
        rule_id=metadata.rule_id,
        message=message,
        severity=metadata.default_severity,
        path=link.document.relative_path,
        line=link.occurrence.line,
        column=link.occurrence.column,
        target=link.occurrence.target,
        fix=fix,
    )
