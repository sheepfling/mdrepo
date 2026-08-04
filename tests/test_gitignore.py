"""Git-ignore hierarchy and durable-target policy coverage."""

import os
from pathlib import Path

import pytest

from mdrepo.cli import main
from mdrepo.config import ApplicationConfig
from mdrepo.exceptions import apply_exceptions
from mdrepo.files import collect_project_markdown
from mdrepo.gitignore import GitIgnoreError, TargetDurabilityPolicy
from mdrepo.models import Diagnostic, Severity
from tests.support import RepositoryBuilder


@pytest.mark.parametrize(
    ("pattern", "relative"),
    [
        ("secret.md", "secret.md"),
        ("artifacts/", "artifacts/release.txt"),
        ("*.tmp", "logs/cache.tmp"),
        ("**/generated/*.md", "docs/archive/generated/guide.md"),
        ("docs/**/draft.md", "docs/archive/2026/draft.md"),
    ],
)
def test_durability_policy_matches_gitignore_pattern_forms(
    repository: RepositoryBuilder,
    pattern: str,
    relative: str,
) -> None:
    repository.write_text(".gitignore", f"{pattern}\n")
    target = repository.write_text(relative, "target\n")
    policy = TargetDurabilityPolicy.from_repository(
        root=repository.root,
        exclude_patterns=(),
    )

    assert policy.classify(target).gitignored is True


def test_durability_policy_honors_gitignore_and_mdrepo_overrides(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(
        ".gitignore",
        "*.md\n!README.md\n!docs/keep.md\n",
    )
    readme = repository.write_text("README.md", "# Root\n")
    keep = repository.write_text("docs/keep.md", "# Keep\n")
    drop = repository.write_text("docs/drop.md", "# Drop\n")
    artifact = repository.write_text("artifacts/keep.txt", "artifact\n")
    policy = TargetDurabilityPolicy.from_repository(
        root=repository.root,
        exclude_patterns=("artifacts/**", "!artifacts/keep.txt"),
    )

    assert policy.classify(readme).excluded is False
    assert policy.classify(keep).excluded is False
    assert policy.classify(drop).gitignored is True
    assert policy.classify(artifact).mdrepo_excluded is False


def test_gitignore_cannot_reinclude_descendant_without_reincluding_parent(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(".gitignore", "ignored/\n!ignored/keep.md\n")
    target = repository.write_text("ignored/keep.md", "target\n")
    policy = TargetDurabilityPolicy.from_repository(
        root=repository.root,
        exclude_patterns=(),
    )

    assert policy.classify(target).gitignored is True


def test_gitignore_can_reinclude_parent_before_descendant(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(
        ".gitignore",
        "ignored/\n!ignored/\n!ignored/keep.md\n",
    )
    target = repository.write_text("ignored/keep.md", "target\n")
    policy = TargetDurabilityPolicy.from_repository(
        root=repository.root,
        exclude_patterns=(),
    )

    assert policy.classify(target).gitignored is False


def test_nested_gitignore_is_applied_to_target(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text("docs/.gitignore", "drafts/\n")
    target = repository.write_text("docs/drafts/guide.md", "target\n")
    policy = TargetDurabilityPolicy.from_repository(
        root=repository.root,
        exclude_patterns=(),
    )

    assert policy.classify(target).gitignored is True


def test_durability_handles_spaces_newlines_and_long_names(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(".gitignore", "ignored/\n")
    relative_paths = (
        "ignored/with spaces.md",
        f"ignored/{'x' * 160}.md",
    )
    targets = [repository.write_text(relative, "target\n") for relative in relative_paths]
    policy = TargetDurabilityPolicy.from_repository(
        root=repository.root,
        exclude_patterns=(),
    )

    assert all(policy.classify(target).gitignored for target in targets)


@pytest.mark.skipif(os.name == "nt", reason="Windows filenames cannot contain newlines")
def test_durability_handles_newline_names(repository: RepositoryBuilder) -> None:
    repository.write_text(".gitignore", "ignored/\n")
    target = repository.write_text("ignored/with\nnewline.md", "target\n")
    policy = TargetDurabilityPolicy.from_repository(
        root=repository.root,
        exclude_patterns=(),
    )

    assert policy.classify(target).gitignored is True


def test_repeated_classification_uses_current_gitignore_contents(
    repository: RepositoryBuilder,
) -> None:
    ignore = repository.root / ".gitignore"
    target = repository.write_text("scratch/guide.md", "target\n")
    ignore.write_text("scratch/\n", encoding="utf-8")
    policy = TargetDurabilityPolicy.from_repository(
        root=repository.root,
        exclude_patterns=(),
    )

    assert policy.classify(target).gitignored is True

    ignore.write_text("other-directory/\n", encoding="utf-8")

    assert policy.classify(target).gitignored is False


def test_durability_policy_does_not_require_git_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    (tmp_path / ".gitignore").write_text("scratch/\n", encoding="utf-8")
    (tmp_path / "scratch").mkdir()
    (tmp_path / "scratch" / "guide.md").write_text("# Scratch\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("[Scratch](scratch/guide.md)\n", encoding="utf-8")

    assert main(["check", "."]) == 1
    assert "MDR006" in capsys.readouterr().out


def test_unreadable_gitignore_is_a_reported_cli_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_bytes(b"\xff\xfe")
    (tmp_path / "target.txt").write_text("target\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("[Target](target.txt)\n", encoding="utf-8")

    assert main(["check", "."]) == 2
    assert "unable to read repository .gitignore" in capsys.readouterr().err


def test_malformed_gitignore_is_a_reported_cli_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_text("bad\\\n", encoding="utf-8")
    (tmp_path / "target.txt").write_text("target\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("[Target](target.txt)\n", encoding="utf-8")

    assert main(["check", "."]) == 2
    error = capsys.readouterr().err
    assert "invalid Git-ignore pattern" in error
    assert "bad\\" in error


def test_malformed_discovery_pattern_is_a_reported_policy_error(
    repository: RepositoryBuilder,
) -> None:
    config = ApplicationConfig.model_validate({"include": ["bad\\"]})

    with pytest.raises(GitIgnoreError, match="mdrepo include policy"):
        collect_project_markdown(root=repository.root, config=config)


def test_malformed_exception_pattern_is_a_reported_policy_error(
    repository: RepositoryBuilder,
) -> None:
    config = ApplicationConfig.model_validate(
        {
            "exceptions": [
                {
                    "id": "bad-path",
                    "rule": "MDR001",
                    "path": "bad\\",
                    "reason": "test malformed path",
                }
            ]
        }
    )

    with pytest.raises(GitIgnoreError, match="exception 'bad-path'"):
        apply_exceptions(
            diagnostics=(
                Diagnostic(rule_id="MDR001", message="finding", severity=Severity.ERROR),
            ),
            config=config,
        )
