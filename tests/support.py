"""Reusable pseudo-repository helpers for integration tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from mdrepo.cli import main

@dataclass(frozen=True, slots=True)
class RepositoryBuilder:
    """Create and invoke mdrepo against one isolated repository root."""

    root: Path

    def path(self, relative: str | Path) -> Path:
        """Return a validated path beneath the repository root."""

        candidate = (self.root / Path(relative)).resolve()
        if not candidate.is_relative_to(self.root.resolve()):
            raise ValueError(f"test path escapes repository root: {relative}")
        return candidate

    def write_text(
            self,
            relative: str | Path,
            text: str,
            *,
            encoding: str = "utf-8",
    ) -> Path:
        """Write text beneath the repository root and return its path."""

        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding=encoding)
        return path

    def write_bytes(self, relative: str | Path, data: bytes) -> Path:
        """Write raw bytes beneath the repository root and return its path."""

        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def markdown(self, relative: str | Path, text: str) -> Path:
        """Write one UTF-8 Markdown document."""

        return self.write_text(relative, text)

    def configure(self, toml: str) -> Path:
        """Replace the repository's minimal test configuration with TOML."""

        normalized = toml.rstrip() + "\n"
        return self.write_text("pyproject.toml", normalized)

    def read_text(self, relative: str | Path, *, encoding: str = "utf-8") -> str:
        """Read text from a repository-relative path."""

        return self.path(relative).read_text(encoding=encoding)

    def run(self, monkeypatch: pytest.MonkeyPatch, *arguments: str) -> int:
        """Run the CLI with this repository as the current working directory."""

        monkeypatch.chdir(self.root)
        return main(list(arguments))
