"""Git-ignore hierarchy and durable-target policy coverage."""

import os
from pathlib import Path

import pytest

from mdrepo import GitIgnoreDecision, GitIgnorePolicy, GitIgnoreWalker
from mdrepo import is_gitignored as public_is_gitignored
from mdrepo.cli import main
from mdrepo.config import ApplicationConfig
from mdrepo.exceptions import apply_exceptions
from mdrepo.files import collect_project_markdown
from mdrepo.gitignore import (
    GitIgnoreError,
    TargetDurabilityPolicy,
    is_gitignored,
    matches_gitignore,
    parse_gitignore,
)
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


def test_is_gitignored_is_a_pathlike_programmatic_endpoint(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(".gitignore", "scratch/\n!scratch/\n!scratch/keep.md\nscratch/drop.md\n")
    ignored = repository.write_text("scratch/drop.md", "drop\n")
    kept = repository.write_text("scratch/keep.md", "keep\n")

    assert is_gitignored(repository.root, "scratch/drop.md") is True
    assert public_is_gitignored(str(repository.root), str(kept)) is False
    assert is_gitignored(repository.root, kept) is False
    assert is_gitignored(repository.root, ignored) is True


def test_policy_and_walker_can_be_composed(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(".gitignore", "generated/\n")
    kept = repository.write_text("docs/guide.md", "guide\n")
    repository.write_text("generated/output.md", "output\n")
    policy = GitIgnorePolicy(repository.root)
    walker = GitIgnoreWalker(repository.root, policy=policy)

    assert policy.is_ignored(kept) is False
    assert kept in tuple(walker.iter_files(ignored=False))


def test_is_gitignored_rejects_targets_outside_the_root(
    repository: RepositoryBuilder,
) -> None:
    outside = repository.root.parent / "outside.md"

    with pytest.raises(ValueError, match="inside repository root"):
        is_gitignored(repository.root, outside)


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


def test_directory_only_pattern_does_not_ignore_regular_file(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(".gitignore", "build/\n")
    target = repository.write_text("build", "regular file\n")
    policy = TargetDurabilityPolicy.from_repository(
        root=repository.root,
        exclude_patterns=(),
    )

    assert policy.classify(target).gitignored is False


def test_directory_only_pattern_matches_descendant_files() -> None:
    spec = parse_gitignore(["build/"], source="test policy")

    assert matches_gitignore(spec, "build", is_directory=False) is False
    assert matches_gitignore(spec, "build", is_directory=True) is True
    assert matches_gitignore(spec, "build/artifact.md", is_directory=False) is True


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


def test_nested_gitignore_can_override_a_root_rule(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(".gitignore", "*.md\n")
    repository.write_text("docs/.gitignore", "!keep.md\n")
    kept = repository.write_text("docs/keep.md", "# Keep\n")
    dropped = repository.write_text("docs/drop.md", "# Drop\n")

    assert is_gitignored(repository.root, kept) is False
    assert is_gitignored(repository.root, dropped) is True


def test_is_gitignored_rejects_a_non_directory_root(tmp_path: Path) -> None:
    root_file = tmp_path / "root.txt"
    root_file.write_text("not a repository root\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a directory"):
        is_gitignored(root_file, "target.md")


def test_gitignore_engine_applies_initial_excludes_and_walk_filters(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(".gitignore", "ignored/\n")
    repository.write_text("README.md", "# Root\n")
    repository.write_text("ignored/by-gitignore.md", "ignored\n")
    repository.write_text("generated/by-initial-policy.md", "generated\n")
    repository.write_text("docs/guide.md", "# Guide\n")
    policy = GitIgnorePolicy(repository.root, initial_excludes=("generated/**",))
    walker = GitIgnoreWalker(repository.root, policy=policy)

    def walked_files(ignored: bool | None) -> set[str]:
        return {
            (directory / name).relative_to(repository.root).as_posix()
            for directory, _, filenames in walker.walk(ignored=ignored)
            for name in filenames
        }

    assert walked_files(None) == {
        ".gitignore",
        "README.md",
        "docs/guide.md",
        "generated/by-initial-policy.md",
        "ignored/by-gitignore.md",
        "pyproject.toml",
    }
    assert walked_files(True) == {
        "generated/by-initial-policy.md",
        "ignored/by-gitignore.md",
    }
    assert walked_files(False) == {
        ".gitignore",
        "README.md",
        "docs/guide.md",
        "pyproject.toml",
    }
    assert policy.is_ignored("generated/by-initial-policy.md") is True


def test_gitignore_engine_batch_checks_share_a_fresh_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(".gitignore", "docs/ignored/\n")
    ignored = repository.write_text("docs/ignored/guide.md", "ignored\n")
    kept = repository.write_text("docs/guide.md", "kept\n")
    engine = GitIgnorePolicy(repository.root)
    loaded: list[Path] = []
    original_read_text = Path.read_text

    def recording_read_text(
        path: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        if path.name == ".gitignore":
            loaded.append(path)
        return original_read_text(path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", recording_read_text)

    assert engine.is_ignored_many((ignored, kept)) == (True, False)
    assert loaded.count(repository.root / ".gitignore") == 1

    (repository.root / ".gitignore").write_text("docs/\n", encoding="utf-8")
    assert engine.is_ignored_many((kept,)) == (True,)


def test_gitignore_engine_explains_matching_source_and_line(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(".gitignore", "# generated files\n\nignored/\n")
    target = repository.write_text("ignored/guide.md", "ignored\n")
    engine = GitIgnorePolicy(repository.root)

    decision = engine.explain(target)

    assert decision == GitIgnoreDecision(
        path=target.resolve(),
        ignored=True,
        source=f"repository .gitignore {repository.root / '.gitignore'}",
        pattern="ignored/",
        line=3,
    )


def test_gitignore_engine_explains_initial_exclusions_and_unmatched_paths(
    repository: RepositoryBuilder,
) -> None:
    kept = repository.write_text("docs/guide.md", "guide\n")
    generated = repository.write_text("generated/guide.md", "generated\n")
    engine = GitIgnorePolicy(repository.root, initial_excludes=("generated/**",))

    assert engine.explain(generated) == GitIgnoreDecision(
        path=generated.resolve(),
        ignored=True,
        source="initial Git-ignore exclusions",
        pattern="generated/**",
        line=1,
    )
    assert engine.explain(kept) == GitIgnoreDecision(path=kept.resolve(), ignored=False)


def test_gitignore_engine_explains_parent_ignore_when_descendant_is_not_reincluded(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(".gitignore", "ignored/\n!ignored/keep.md\n")
    target = repository.write_text("ignored/keep.md", "keep\n")

    decision = GitIgnorePolicy(repository.root).explain(target)

    assert decision.ignored is True
    assert decision.pattern == "ignored/"
    assert decision.line == 1


def test_gitignore_engine_iter_files_yields_only_files(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(".gitignore", "ignored/\n")
    repository.write_text("README.md", "root\n")
    repository.write_text("docs/guide.md", "guide\n")
    repository.write_text("ignored/generated.md", "generated\n")
    engine = GitIgnoreWalker(repository.root)

    ignored_files = {
        path.relative_to(repository.root).as_posix() for path in engine.iter_files(ignored=True)
    }
    unignored_files = {
        path.relative_to(repository.root).as_posix() for path in engine.iter_files(ignored=False)
    }

    assert ignored_files == {"ignored/generated.md"}
    assert "README.md" in unignored_files
    assert "docs/guide.md" in unignored_files
    assert all(path not in {"ignored", "docs"} for path in unignored_files)


def test_gitignore_engine_prunes_ignored_directories_and_supports_topdown_pruning(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(".gitignore", "ignored/\n")
    repository.write_text("ignored/nested/hidden.md", "hidden\n")
    repository.write_text("kept/nested/visible.md", "visible\n")
    engine = GitIgnoreWalker(repository.root)

    unignored_directories = {
        directory.relative_to(repository.root).as_posix()
        for directory, _, _ in engine.walk(ignored=False)
    }
    assert all(not path.startswith("ignored") for path in unignored_directories)

    visited: set[str] = set()
    for directory, dir_names, _ in engine.walk():
        relative = directory.relative_to(repository.root).as_posix()
        visited.add(relative)
        if directory == repository.root:
            dir_names[:] = [name for name in dir_names if name != "kept"]

    assert "ignored" in visited
    assert "ignored/nested" in visited
    assert "kept" not in visited
    assert "kept/nested" not in visited


def test_gitignore_engine_does_not_prune_contents_only_ignored_directories(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(".gitignore", "docs/**\n!docs/keep.md\n")
    repository.write_text("docs/keep.md", "keep\n")
    repository.write_text("docs/drop.md", "drop\n")
    engine = GitIgnoreWalker(repository.root)

    unignored_files = {
        (directory / name).relative_to(repository.root).as_posix()
        for directory, _, filenames in engine.walk(ignored=False)
        for name in filenames
    }

    assert "docs/keep.md" in unignored_files
    assert "docs/drop.md" not in unignored_files


def test_gitignore_engine_ignored_walk_descends_through_unignored_directories(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text(".gitignore", "docs/drafts/\n")
    repository.write_text("docs/guide.md", "guide\n")
    repository.write_text("docs/drafts/hidden.md", "hidden\n")
    engine = GitIgnoreWalker(repository.root)

    ignored_files = {
        (directory / name).relative_to(repository.root).as_posix()
        for directory, _, filenames in engine.walk(ignored=True)
        for name in filenames
    }

    assert ignored_files == {"docs/drafts/hidden.md"}


def test_gitignore_engine_walk_can_start_at_a_subdirectory(
    repository: RepositoryBuilder,
) -> None:
    repository.write_text("docs/guide.md", "guide\n")
    repository.write_text("docs/nested/reference.md", "reference\n")
    engine = GitIgnoreWalker(repository.root)

    directories = {
        directory.relative_to(repository.root).as_posix() for directory, _, _ in engine.walk("docs")
    }

    assert directories == {"docs", "docs/nested"}


def test_gitignore_engine_walk_skips_symlinked_entries(
    repository: RepositoryBuilder,
) -> None:
    target = repository.write_text("docs/guide.md", "guide\n")
    link = repository.root / "docs" / "link.md"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks are not supported in this environment")

    filenames = {
        (directory / name).relative_to(repository.root).as_posix()
        for directory, _, names in GitIgnoreWalker(repository.root).walk()
        for name in names
    }

    assert "docs/guide.md" in filenames
    assert "docs/link.md" not in filenames


def test_gitignore_engine_rejects_following_symlinks(
    repository: RepositoryBuilder,
) -> None:
    engine = GitIgnoreWalker(repository.root)

    with pytest.raises(ValueError, match="does not follow symlinks"):
        tuple(engine.walk(follow_links=True))


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
            diagnostics=(Diagnostic(rule_id="MDR001", message="finding", severity=Severity.ERROR),),
            config=config,
        )
