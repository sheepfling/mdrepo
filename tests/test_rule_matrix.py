"""Direct rule behavior for the repository-policy contract."""

from mdrepo.config import ApplicationConfig
from mdrepo.graph import DocumentGraph
from mdrepo.markdown import MarkdownParser
from mdrepo.resolution import resolve_local_target
from mdrepo.rules import (
    AbsoluteLocalLinkRule,
    LocalTargetCaseRule,
    MissingGraphRootRule,
    MissingLocalTargetRule,
    NonPosixLocalLinkRule,
    PolicyLink,
    RepositoryEscapeRule,
    RuleContext,
)
from tests.support import RepositoryBuilder


def _context(
    repository: RepositoryBuilder,
    text: str,
    config_data: dict[str, object],
) -> RuleContext:
    source = repository.markdown("README.md", text)
    document = MarkdownParser().parse(
        path=source,
        root=repository.root,
        text=text,
    )
    local_links = tuple(
        PolicyLink(
            document=document,
            occurrence=occurrence,
            local=resolve_local_target(
                root=repository.root,
                document=document,
                occurrence=occurrence,
            ),
        )
        for occurrence in document.policy_occurrences
    )
    return RuleContext(
        root=repository.root,
        config=ApplicationConfig.model_validate(config_data),
        documents={document.path: document},
        selected_documents=(document,),
        policy_links=local_links,
        graph=None,
    )


def test_link_rules_respect_portability_toggles(repository: RepositoryBuilder) -> None:
    context = _context(
        repository,
        "[Back](docs\\guide.md)\n[Root](/README.md)\n[Escape](../outside.md)\n[Missing](missing.md)\n",
        {"links": {"check-missing-targets": True}},
    )

    assert len(NonPosixLocalLinkRule().check(context)) == 1
    assert len(AbsoluteLocalLinkRule().check(context)) == 1
    assert len(RepositoryEscapeRule().check(context)) == 1
    assert len(MissingLocalTargetRule().check(context)) == 2

    relaxed = _context(
        repository,
        "[Root](/README.md)\n[Escape](../outside.md)\n",
        {
            "links": {
                "allow-root-relative": True,
                "allow-outside-root": True,
                "require-posix": False,
            }
        },
    )
    assert AbsoluteLocalLinkRule().check(relaxed) == ()
    assert RepositoryEscapeRule().check(relaxed) == ()
    assert NonPosixLocalLinkRule().check(relaxed) == ()


def test_missing_target_rule_distinguishes_images_and_absolute_routes(
    repository: RepositoryBuilder,
) -> None:
    context = _context(
        repository,
        "![Missing](assets/nope.png)\n[Root](/missing.md)\n",
        {"links": {"check-missing-targets": True, "allow-root-relative": True}},
    )

    diagnostics = MissingLocalTargetRule().check(context)
    assert [diagnostic.message for diagnostic in diagnostics] == [
        "local image target does not exist: assets/nope.png",
        "local link target does not exist: /missing.md",
    ]


def test_case_rule_and_missing_graph_root_are_guarded(repository: RepositoryBuilder) -> None:
    repository.markdown("README.md", "# Root\n")
    repository.markdown("Docs/Guide.md", "# Guide\n")
    context = _context(repository, "[Guide](docs/guide.md)\n", {})
    assert LocalTargetCaseRule().check(context)[0].rule_id == "MDR005"

    no_root = RuleContext(
        root=repository.root,
        config=ApplicationConfig.model_validate({"orphans": {"enabled": True}}),
        documents=context.documents,
        selected_documents=context.selected_documents,
        policy_links=(),
        graph=DocumentGraph(edges={}, roots=(), reachable=frozenset()),
    )
    assert MissingGraphRootRule().check(no_root)[0].rule_id == "MDR100"
