"""Repository-aware Markdown policy CLI and stable package metadata."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

from mdrepo._metadata import DISTRIBUTION_NAME as _DISTRIBUTION_NAME

__all__ = ["__version__"]

try:
    __version__ = package_version(_DISTRIBUTION_NAME)
except PackageNotFoundError:
    __version__ = "0+unknown"
