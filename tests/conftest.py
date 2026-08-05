"""Shared test isolation fixtures."""

from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from tests.constants import TOOL_TABLE
from tests.support import RepositoryBuilder


@pytest.fixture
def tmp_path() -> Iterator[Path]:
    """Provide temporary repositories inside the checkout for predictable cleanup."""

    repository_tmp = Path(__file__).resolve().parents[1] / ".tmp"
    repository_tmp.mkdir(exist_ok=True, parents=True)
    with TemporaryDirectory(prefix="pytest-", dir=repository_tmp) as directory:
        test_root = Path(directory)
        (test_root / "pyproject.toml").write_text(f"{TOOL_TABLE}\n", encoding="utf-8")
        yield test_root


@pytest.fixture
def repository(tmp_path: Path) -> RepositoryBuilder:
    """Provide a builder for readable, isolated repository integration tests."""

    return RepositoryBuilder(tmp_path)
