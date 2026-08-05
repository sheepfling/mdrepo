"""Supported package import surface."""

import mdrepo


def test_package_root_exposes_version_and_gitignore_endpoint() -> None:
    assert mdrepo.__all__ == [
        "GitIgnoreDecision",
        "GitIgnoreEngine",
        "GitIgnoreError",
        "__version__",
        "is_gitignored",
    ]
    assert mdrepo.GitIgnoreDecision is not None
    assert callable(mdrepo.GitIgnoreEngine)
    assert callable(mdrepo.is_gitignored)
    assert issubclass(mdrepo.GitIgnoreError, RuntimeError)
    assert not hasattr(mdrepo, "Diagnostic")
    assert not hasattr(mdrepo, "Fix")
    assert not hasattr(mdrepo, "RuleMetadata")
    assert not hasattr(mdrepo, "Severity")
