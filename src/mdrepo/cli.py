"""Command-line interface for focused repository Markdown policy checks."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from mdrepo import __version__
from mdrepo.config import ConfigurationError, LoadedConfig, load_configuration
from mdrepo.engine import EngineError, RunResult, run_repository
from mdrepo.files import FileDiscoveryError
from mdrepo.fixes import FixError, apply_fixes, collect_fixes
from mdrepo.graph import DocumentGraph
from mdrepo.models import OutputFormat, Severity
from mdrepo.reporting import should_fail, write_diagnostics
from mdrepo.rules import RULE_METADATA


class CliError(RuntimeError):
    """Raised for invalid command combinations discovered after parsing."""
####




def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit status."""

    parser = _build_parser()
    namespace = parser.parse_args(list(argv) if argv is not None else None)
    try:
        loaded = _load_for_namespace(namespace)
        return _dispatch(namespace=namespace, loaded=loaded, stdout=sys.stdout, stderr=sys.stderr)
    except (
        CliError,
        ConfigurationError,
        EngineError,
        FileDiscoveryError,
        FixError,
    ) as error:
        print(f"mdrepo: error: {error}", file=sys.stderr)
        return 2
    ####
####




def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False, argument_default=argparse.SUPPRESS)
    common.add_argument("--root", type=Path, help="Explicit repository root.")
    common.add_argument(
        "--config",
        action="append",
        type=Path,
        help="Additional TOML configuration overlay. Repeat to layer files.",
    )
    common.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        help="Typed dotted TOML override. Repeat for multiple values.",
    )
    common.add_argument(
        "--format",
        choices=[item.value for item in OutputFormat],
        help="Diagnostic output format.",
    )
    common.add_argument(
        "--fail-on",
        choices=[item.value for item in Severity],
        help="Lowest diagnostic severity that produces exit status 1.",
    )
    common.add_argument(
        "--select",
        action="append",
        metavar="RULES",
        help="Run only comma-separated rule IDs. Repeat to extend the selection.",
    )
    common.add_argument(
        "--ignore",
        action="append",
        metavar="RULES",
        help="Ignore comma-separated rule IDs. Repeat to extend the ignore set.",
    )

    parser = argparse.ArgumentParser(
        prog="mdrepo",
        description=(
            "Repository-aware Markdown link and document-graph policy checks that complement rumdl."
        ),
        parents=[common],
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", parents=[common], help="Check repository policy.")
    check.add_argument(
        "paths",
        nargs="*",
        help="Markdown files or directories; defaults to the project.",
    )
    check.add_argument(
        "--show-suppressed",
        action="store_true",
        help="Render diagnostics hidden by structured exceptions.",
    )
    check.add_argument("--summary", action="store_true", help="Print a compact count summary.")

    fix = subparsers.add_parser("fix", parents=[common], help="Apply only unambiguous safe fixes.")
    fix.add_argument(
        "paths",
        nargs="*",
        help="Markdown files or directories; defaults to the project.",
    )
    fix.add_argument("--dry-run", action="store_true", help="Show diffs without modifying files.")
    fix.add_argument(
        "--diff",
        action="store_true",
        help="Print unified diffs in addition to applying changes.",
    )
    fix.add_argument(
        "--show-suppressed",
        action="store_true",
        help="Render diagnostics hidden by structured exceptions after fixing.",
    )
    fix.add_argument("--summary", action="store_true", help="Print a compact count summary.")

    graph = subparsers.add_parser(
        "graph",
        parents=[common],
        help="Render the repository Markdown document graph.",
    )
    graph.add_argument("paths", nargs="*", help=argparse.SUPPRESS)
    graph.add_argument(
        "--graph-format",
        choices=["text", "json", "dot"],
        default="text",
        help="Graph serialization format.",
    )

    subparsers.add_parser("rules", parents=[common], help="List built-in rule metadata.")
    subparsers.add_parser("config", parents=[common], help="Print resolved configuration as JSON.")
    return parser
####




def _load_for_namespace(namespace: argparse.Namespace) -> LoadedConfig:
    paths = list(getattr(namespace, "paths", []))
    cwd = _configuration_start(paths=paths, explicit_root=getattr(namespace, "root", None))
    overrides = list(getattr(namespace, "set", []))

    output_format = getattr(namespace, "format", None)
    if output_format is not None:
        overrides.append(f"output={json.dumps(output_format)}")
    ####
    fail_on = getattr(namespace, "fail_on", None)
    if fail_on is not None:
        overrides.append(f"fail-on={json.dumps(fail_on)}")
    ####
    selected = _split_rule_arguments(getattr(namespace, "select", []))
    if selected:
        overrides.append(f"rules.select={json.dumps(selected)}")
    ####
    ignored = _split_rule_arguments(getattr(namespace, "ignore", []))
    if ignored:
        overrides.append(f"rules.ignore={json.dumps(ignored)}")
    ####

    return load_configuration(
        cwd=cwd,
        root_override=getattr(namespace, "root", None),
        config_paths=list(getattr(namespace, "config", [])),
        overrides=overrides,
    )
####




def _configuration_start(*, paths: list[str], explicit_root: Path | None) -> Path:
    if explicit_root is not None or not paths:
        return Path.cwd()
    ####
    first = Path(paths[0]).expanduser()
    if not first.is_absolute():
        first = Path.cwd() / first
    ####
    if first.exists() and first.is_file():
        return first.resolve().parent
    ####
    if first.exists() and first.is_dir():
        return first.resolve()
    ####
    return Path.cwd()
####




def _dispatch(
    *,
    namespace: argparse.Namespace,
    loaded: LoadedConfig,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    command = str(namespace.command)
    if command == "check":
        return _check(namespace=namespace, loaded=loaded, stdout=stdout, stderr=stderr)
    ####
    if command == "fix":
        return _fix(namespace=namespace, loaded=loaded, stdout=stdout, stderr=stderr)
    ####
    if command == "graph":
        return _graph(namespace=namespace, loaded=loaded, stdout=stdout)
    ####
    if command == "rules":
        return _rules(loaded=loaded, stdout=stdout)
    ####
    if command == "config":
        return _config(loaded=loaded, stdout=stdout)
    ####
    raise CliError(f"unknown command: {command}")
####




def _check(
    *,
    namespace: argparse.Namespace,
    loaded: LoadedConfig,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    result = run_repository(
        loaded_config=loaded,
        requested_paths=list(namespace.paths),
    )
    rendered = result.diagnostics
    if namespace.show_suppressed:
        rendered = tuple((*rendered, *result.suppressed))
    ####
    write_diagnostics(
        diagnostics=rendered,
        output_format=loaded.model.output,
        stream=stdout,
    )
    if namespace.summary:
        _write_summary(result=result, stream=stderr)
    ####
    return int(should_fail(diagnostics=result.diagnostics, threshold=loaded.model.fail_on))
####




def _fix(
    *,
    namespace: argparse.Namespace,
    loaded: LoadedConfig,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    if (namespace.dry_run or namespace.diff) and loaded.model.output is not OutputFormat.TEXT:
        raise CliError("fix diffs require --format text")
    ####

    initial = run_repository(
        loaded_config=loaded,
        requested_paths=list(namespace.paths),
    )
    fixes = collect_fixes(initial.diagnostics)
    fix_result = apply_fixes(
        fixes=fixes,
        root=loaded.root,
        encoding=loaded.model.encoding,
        dry_run=bool(namespace.dry_run),
    )

    if namespace.dry_run or namespace.diff:
        for diff in fix_result.diffs:
            stdout.write(diff)
            if diff and not diff.endswith("\n"):
                stdout.write("\n")
            ####
        ####
    ####

    if namespace.dry_run:
        remaining = initial
    else:
        remaining = run_repository(
            loaded_config=loaded,
            requested_paths=list(namespace.paths),
        )
        rendered = remaining.diagnostics
        if namespace.show_suppressed:
            rendered = tuple((*rendered, *remaining.suppressed))
        ####
        write_diagnostics(
            diagnostics=rendered,
            output_format=loaded.model.output,
            stream=stdout,
        )
    ####

    print(
        f"mdrepo: {'would fix' if namespace.dry_run else 'fixed'} "
        f"{fix_result.applied_count} issue(s) in {len(fix_result.changed_files)} file(s)",
        file=stderr,
    )
    if namespace.summary:
        _write_summary(result=remaining, stream=stderr)
    ####

    if namespace.dry_run and fix_result.applied_count:
        return 1
    ####
    return int(should_fail(diagnostics=remaining.diagnostics, threshold=loaded.model.fail_on))
####




def _graph(
    *,
    namespace: argparse.Namespace,
    loaded: LoadedConfig,
    stdout: TextIO,
) -> int:
    if namespace.paths:
        raise CliError("graph is repository-wide and does not accept path filters")
    ####
    result = run_repository(
        loaded_config=loaded,
        requested_paths=[],
        force_graph=True,
    )
    if result.graph is None:
        raise CliError("unable to construct the document graph")
    ####
    _write_graph(
        graph=result.graph,
        root=result.root,
        graph_format=namespace.graph_format,
        stream=stdout,
    )
    return 0
####




def _rules(*, loaded: LoadedConfig, stdout: TextIO) -> int:
    if loaded.model.output is OutputFormat.JSON:
        json.dump(
            [
                {
                    "default_severity": metadata.default_severity.value,
                    "description": metadata.description,
                    "fixable": metadata.fixable,
                    "name": metadata.name,
                    "rule_id": metadata.rule_id,
                }
                for metadata in RULE_METADATA
            ],
            stdout,
            indent=2,
            sort_keys=True,
        )
        stdout.write("\n")
        return 0
    ####

    for metadata in RULE_METADATA:
        fixable = "fixable" if metadata.fixable else "check-only"
        stdout.write(
            f"{metadata.rule_id}  {metadata.default_severity.value:<7}  "
            f"{fixable:<10}  {metadata.name}\n"
        )
        stdout.write(f"  {metadata.description}\n")
    ####
    return 0
####




def _config(*, loaded: LoadedConfig, stdout: TextIO) -> int:
    payload = {
        "config": loaded.model.model_dump(by_alias=True, mode="json"),
        "root": str(loaded.root),
        "sources": [str(path) for path in loaded.sources],
    }
    json.dump(payload, stdout, indent=2, sort_keys=True)
    stdout.write("\n")
    return 0
####




def _write_graph(
    *,
    graph: DocumentGraph,
    root: Path,
    graph_format: str,
    stream: TextIO,
) -> None:
    relative_edges = {
        source.relative_to(root).as_posix(): sorted(
            target.relative_to(root).as_posix() for target in targets
        )
        for source, targets in graph.edges.items()
    }
    roots = [path.relative_to(root).as_posix() for path in graph.roots]
    unreachable = sorted(
        path.relative_to(root).as_posix() for path in graph.edges if path not in graph.reachable
    )

    if graph_format == "json":
        json.dump(
            {"edges": relative_edges, "roots": roots, "unreachable": unreachable},
            stream,
            indent=2,
            sort_keys=True,
        )
        stream.write("\n")
        return
    ####

    if graph_format == "dot":
        stream.write("digraph markdown {\n")
        for root_path in roots:
            stream.write(f"  {json.dumps(root_path)} [shape=doublecircle];\n")
        ####
        for source, targets in relative_edges.items():
            if not targets:
                stream.write(f"  {json.dumps(source)};\n")
                continue
            ####
            for target in targets:
                stream.write(f"  {json.dumps(source)} -> {json.dumps(target)};\n")
            ####
        ####
        stream.write("}\n")
        return
    ####

    stream.write(f"roots: {', '.join(roots) if roots else '(none)'}\n")
    for source, targets in relative_edges.items():
        rendered = ", ".join(targets) if targets else "(none)"
        stream.write(f"{source} -> {rendered}\n")
    ####
    stream.write(f"unreachable: {', '.join(unreachable) if unreachable else '(none)'}\n")
####




def _write_summary(*, result: RunResult, stream: TextIO) -> None:
    errors = sum(diagnostic.severity is Severity.ERROR for diagnostic in result.diagnostics)
    warnings = sum(diagnostic.severity is Severity.WARNING for diagnostic in result.diagnostics)
    infos = sum(diagnostic.severity is Severity.INFO for diagnostic in result.diagnostics)
    stream.write(
        f"mdrepo: {errors} error(s), {warnings} warning(s), {infos} info finding(s), "
        f"{len(result.suppressed)} suppressed\n"
    )
####




def _split_rule_arguments(values: list[str]) -> list[str]:
    rules: list[str] = []
    for value in values:
        for item in value.split(","):
            normalized = item.strip().upper()
            if normalized and normalized not in rules:
                rules.append(normalized)
            ####
        ####
    ####
    return rules
####


