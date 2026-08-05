"""Repository-aware Markdown policy CLI and stable consumer helpers.

The supported consumer interfaces are the ``mdrepo`` command, its
``python -m mdrepo`` equivalent, and the focused Git-ignore endpoint with its
``GitIgnorePolicy``, ``GitIgnoreWalker``, ``GitIgnoreDecision``, and ``GitIgnoreError``
types. Internal modules are
otherwise not exported as stable programmatic APIs.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

from mdrepo._metadata import DISTRIBUTION_NAME as _DISTRIBUTION_NAME
from mdrepo.gitignore import (
    GitIgnoreDecision,
    GitIgnoreError,
    GitIgnorePolicy,
    GitIgnoreWalker,
    is_gitignored,
)

__all__ = [
    "GitIgnoreDecision",
    "GitIgnoreError",
    "GitIgnorePolicy",
    "GitIgnoreWalker",
    "__version__",
    "is_gitignored",
]

try:
    __version__ = package_version(_DISTRIBUTION_NAME)
except PackageNotFoundError:
    __version__ = "0+unknown"
