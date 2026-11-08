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
    # Keep this patch separate from the test's monkeypatch fixture so its cwd
    # changes are undone before TemporaryDirectory cleanup (required on Windows).
    with (
        TemporaryDirectory(prefix="pytest-", dir=repository_tmp) as directory,
        pytest.MonkeyPatch.context() as environment,
    ):
        test_root = Path(directory)
        # Bound portable Git discovery and keep machine-global ignores out of fixtures.
        (test_root / ".git").mkdir()
        environment.setenv("XDG_CONFIG_HOME", str(test_root / ".git" / "test-config"))
        (test_root / "pyproject.toml").write_text(f"{TOOL_TABLE}\n", encoding="utf-8")
        yield test_root


@pytest.fixture
def repository(tmp_path: Path) -> RepositoryBuilder:
    """Provide a builder for readable, isolated repository integration tests."""

    return RepositoryBuilder(tmp_path)
