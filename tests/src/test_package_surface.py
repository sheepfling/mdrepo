"""Supported package import surface."""

import mdrepo
import mdrepo.gitignore


def test_package_root_exposes_only_version_metadata() -> None:
    assert mdrepo.__all__ == ["__version__"]
    assert not hasattr(mdrepo, "GitIgnorePolicy")
    assert not hasattr(mdrepo, "GitIgnoreWalker")
    assert not hasattr(mdrepo, "is_gitignored")
    assert callable(mdrepo.gitignore.GitIgnorePolicy)
    assert callable(mdrepo.gitignore.GitIgnoreWalker)
    assert issubclass(mdrepo.gitignore.GitIgnoreError, RuntimeError)
    assert not hasattr(mdrepo, "Diagnostic")
    assert not hasattr(mdrepo, "Fix")
    assert not hasattr(mdrepo, "RuleMetadata")
    assert not hasattr(mdrepo, "Severity")
