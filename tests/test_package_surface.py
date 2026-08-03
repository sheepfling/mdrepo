"""Supported package import surface."""

import mdrepo


def test_package_root_exposes_only_version() -> None:
    assert mdrepo.__all__ == ["__version__"]
    assert not hasattr(mdrepo, "Diagnostic")
    assert not hasattr(mdrepo, "Fix")
    assert not hasattr(mdrepo, "RuleMetadata")
    assert not hasattr(mdrepo, "Severity")
