"""Shared test isolation fixtures."""

from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


@pytest.fixture
def tmp_path() -> Iterator[Path]:
    """Provide temporary repositories inside the checkout for predictable cleanup."""

    repository_tmp = Path(__file__).resolve().parents[1] / ".tmp"
    repository_tmp.mkdir(exist_ok=True, parents=True)
    with TemporaryDirectory(prefix="pytest-", dir=repository_tmp) as directory:
        test_root = Path(directory)
        (test_root / "pyproject.toml").write_text("[tool.mdrepo]\n", encoding="utf-8")
        yield test_root
    ####
####


