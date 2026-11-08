"""Small compatibility layer for Python versions supported by mdrepo."""

import sys
from enum import Enum

if sys.version_info >= (3, 11):
    from enum import StrEnum

    import tomllib
else:
    import tomli as tomllib

    class StrEnum(str, Enum):
        """String enum with the formatting behavior introduced in Python 3.11."""

        def __str__(self) -> str:
            return str.__str__(self)


__all__ = ["StrEnum", "tomllib"]
