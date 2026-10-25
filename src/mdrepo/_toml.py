"""Use the standard-library TOML parser, with its backport on Python 3.10."""

import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

__all__ = ["tomllib"]
