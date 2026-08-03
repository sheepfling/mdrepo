"""Repository-aware Markdown policy CLI.

The supported consumer interface is the ``mdrepo`` command and its
``python -m mdrepo`` equivalent. Internal modules are intentionally not
exported as a stable programmatic API yet.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

__all__ = ["__version__"]


try:
    __version__ = package_version("mdrepo")
except PackageNotFoundError:
    __version__ = "0+unknown"
