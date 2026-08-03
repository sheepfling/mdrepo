"""CLI command-surface and reusable repository-fixture coverage."""

import json
from pathlib import Path

import pytest

from tests.support import RepositoryBuilder

def test_repository_builder_rejects_paths_outside_root(repository: RepositoryBuilder) -> None:
    with pytest.raises(ValueError, match="escapes repository root"):
        repository.path(Path("..") / "outside.md")

def test_rules_command_supports_text_and_json_output(
        repository: RepositoryBuilder,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
) -> None:
    assert repository.run(monkeypatch, "rules") == 0
    text_output = capsys.readouterr().out
    assert "MDR001" in text_output
    assert "MDR202" in text_output
    assert "MDR006" not in text_output

    repository.configure('[tool.mdrepo]\noutput = "json"')
    assert repository.run(monkeypatch, "rules") == 0
    records = json.loads(capsys.readouterr().out)
    assert {record["rule_id"] for record in records} >= {"MDR001", "MDR202"}
    assert "MDR006" not in {record["rule_id"] for record in records}

def test_config_command_reports_layered_sources(
        repository: RepositoryBuilder,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
) -> None:
    repository.configure(
        """
[tool.mdrepo]
fail-on = "warning"

[tool.mdrepo.links]
check-case = false
"""
    )
    repository.write_text(".mdrepo.toml", "[links]\nrequire-posix = false\n")

    assert repository.run(monkeypatch, "config") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["root"] == str(repository.root)
    assert payload["sources"] == [
        str(repository.path("pyproject.toml")),
        str(repository.path(".mdrepo.toml")),
    ]
    assert payload["config"]["fail-on"] == "warning"
    assert payload["config"]["links"]["check-case"] is False
    assert payload["config"]["links"]["require-posix"] is False

def test_graph_json_and_path_filter_error(
        repository: RepositoryBuilder,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
) -> None:
    repository.markdown("README.md", "[Guide](docs/guide.md)\n")
    repository.markdown("docs/guide.md", "# Guide\n")

    assert repository.run(monkeypatch, "graph", "--graph-format", "json") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["roots"] == ["README.md"]
    assert payload["edges"]["README.md"] == ["docs/guide.md"]
    assert payload["unreachable"] == []

    assert repository.run(monkeypatch, "graph", "README.md") == 2
    assert "does not accept path filters" in capsys.readouterr().err

def test_github_output_is_emitted_for_policy_diagnostics(
        repository: RepositoryBuilder,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
) -> None:
    repository.markdown("README.md", "[Root](/README.md)\n")

    assert repository.run(monkeypatch, "check", ".", "--format", "github") == 1
    output = capsys.readouterr().out
    assert "::error file=README.md" in output
    assert "title=MDR002" in output

def test_graph_text_and_dot_serializations_cover_empty_and_edge_nodes(
        repository: RepositoryBuilder,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
) -> None:
    repository.markdown("README.md", "[Guide](docs/guide.md)\n")
    repository.markdown("docs/guide.md", "# Guide\n")

    assert repository.run(monkeypatch, "graph") == 0
    text_output = capsys.readouterr().out
    assert "roots: README.md" in text_output
    assert "README.md -> docs/guide.md" in text_output
    assert "unreachable: (none)" in text_output

    assert repository.run(monkeypatch, "graph", "--graph-format", "dot") == 0
    dot_output = capsys.readouterr().out
    assert '"README.md" [shape=doublecircle]' in dot_output
    assert '"README.md" -> "docs/guide.md"' in dot_output

def test_check_summary_and_suppressed_diagnostics_are_explicit(
        repository: RepositoryBuilder,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
) -> None:
    repository.markdown("README.md", "[Root](/README.md)\n")
    repository.configure(
        """
[tool.mdrepo]

[[tool.mdrepo.exceptions]]
id = "root-route"
rule = "MDR002"
path = "README.md"
reason = "The published route is intentionally root-relative."
"""
    )

    assert repository.run(monkeypatch, "check", ".", "--summary") == 0
    output = capsys.readouterr()
    assert output.out == ""
    assert "0 error(s)" in output.err
    assert "1 suppressed" in output.err

    assert repository.run(monkeypatch, "check", ".", "--show-suppressed") == 0
    assert "suppressed by: root-route" in capsys.readouterr().out

def test_fix_dry_run_and_diff_have_distinct_write_behavior(
        repository: RepositoryBuilder,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
) -> None:
    repository.markdown("docs/guide.md", "# Guide\n")
    repository.markdown("README.md", "[Guide](/docs/guide.md)\n")

    assert repository.run(monkeypatch, "fix", ".", "--dry-run") == 1
    dry_run = capsys.readouterr()
    assert "would fix 1 issue(s)" in dry_run.err
    assert repository.read_text("README.md") == "[Guide](/docs/guide.md)\n"
    assert "-" in dry_run.out and "+" in dry_run.out

    assert repository.run(monkeypatch, "fix", ".", "--diff") == 0
    diff = capsys.readouterr()
    assert "fixed 1 issue(s)" in diff.err
    assert "docs/guide.md" in repository.read_text("README.md")
    assert "-" in diff.out and "+" in diff.out
