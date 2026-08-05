"""Test metadata derived from the package under test."""

import mdrepo

PACKAGE_NAME = mdrepo.__name__
TOOL_NAMESPACE = f"tool.{PACKAGE_NAME}"
TOOL_TABLE = f"[{TOOL_NAMESPACE}]"
TOOL_LINKS_TABLE = f"[{TOOL_NAMESPACE}.links]"
TOOL_ORPHANS_TABLE = f"[{TOOL_NAMESPACE}.orphans]"
TOOL_RULES_TABLE = f"[{TOOL_NAMESPACE}.rules]"
TOOL_EXCEPTIONS_TABLE = f"[[{TOOL_NAMESPACE}.exceptions]]"
MODULE_COMMAND = ("-m", PACKAGE_NAME)
PYTEST_COMMAND = ("-m", "pytest")
COVERAGE_ARGUMENT = f"--cov={PACKAGE_NAME}"
