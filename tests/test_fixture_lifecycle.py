"""Temporary repositories must be released before directory cleanup on Windows."""

import os
import subprocess
import sys
from pathlib import Path


def test_temporary_repository_restores_cwd_before_cleanup(tmp_path: Path) -> None:
    """Exercise real pytest teardown order with a platform-independent Windows guard."""
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "conftest.py").write_text(
        """from pathlib import Path
from tempfile import TemporaryDirectory
import tests.conftest as fixtures
from tests.conftest import tmp_path

class GuardedTemporaryDirectory(TemporaryDirectory):
    def cleanup(self):
        assert not Path.cwd().is_relative_to(Path(self.name)), (
            "temporary repository is still the working directory during cleanup"
        )
        super().cleanup()

fixtures.TemporaryDirectory = GuardedTemporaryDirectory
""",
        encoding="utf-8",
    )
    (tmp_path / "test_chdir.py").write_text(
        """def test_chdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
""",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(root), str(root / "src")))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-c", "pytest.ini", "test_chdir.py"],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
