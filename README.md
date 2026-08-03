# mdrepo

> **Portable links. Reachable docs. Exceptions that do not quietly live forever.**

[![CI][ci-badge]][ci]
[![Python 3.11+][python-badge]][python]
[![License: MIT][license-badge]][license]
[![Typing: strict Pyright][typing-badge]][typing]
[![Lint: Ruff][ruff-badge]][ruff]
[![pre-commit][pre-commit-badge]][pre-commit]

Most Markdown linters stop at the file boundary. `mdrepo` starts at the repository boundary.

`mdrepo` is a focused Python 3.11+ CLI for policies that require cross-platform filesystem
semantics or a view of the complete documentation set. It complements [rumdl][rumdl] rather than
replacing it.

It catches repository-level problems such as:

- backslash links and machine-local absolute paths;
- links that escape the repository root;
- path spelling that differs from exact on-disk case;
- Markdown pages unreachable from configured entry documents;
- expired exceptions and exceptions that no longer suppress anything.

`mdrepo` is deterministic and offline. It performs no HTTP crawl, documentation-site build,
Node.js or npm orchestration, subprocess wrapping, or public plugin discovery.

## Quick start

From a checkout, install `mdrepo` as a persistent command and check a repository:

```bash
uv tool install .
mdrepo check /path/to/repository
```

For development inside this repository:

```bash
uv sync --extra dev
uv run python -m mdrepo check .
```

Preview the deliberately narrow safe-fix set before changing files:

```bash
mdrepo fix . --dry-run
mdrepo fix .
```

Diagnostics are stable and source-located:

```text
docs/setup.md:24:15: error MDR001 local destination uses backslashes instead of POSIX '/' separators
  fix: normalize the local destination to a POSIX relative path
notes.md:1:1: error MDR101 Markdown document is unreachable from every configured graph root
  hint: Link the document into the graph or add a narrow structured exception.
```

## Where `mdrepo` fits

> `rumdl` validates Markdown **as documents**. `mdrepo` validates Markdown references **as
> relationships inside a repository**.

| Question | Authority |
|---|---|
| Is the Markdown valid, consistently formatted, and flavor-aware? | `rumdl` |
| Does a relative target or heading fragment exist? | `rumdl` `MD057` and `MD051` |
| Are local paths portable, root-bounded, and cased exactly like the filesystem? | `mdrepo` |
| Is each page reachable from a configured documentation root? | `mdrepo` |
| Are policy exceptions justified, current, and still necessary? | `mdrepo` |
| Does a generated documentation site build and route correctly? | The site build |
| Does an external URL currently respond? | A dedicated network checker |

The tools are independent. `mdrepo` does not invoke rumdl, consume its diagnostics, interpret its
inline suppressions, or forward its configuration. Each tool owns its own rules, configuration,
output, and exit status.

See the [complete responsibility boundary](docs/responsibility-boundary.md) for overlap policy,
MkDocs guidance, guarantees, and non-goals.

## What the focused tool adds

| Capability | What it protects against |
|---|---|
| Portable destinations | Backslashes, local absolute paths, and disallowed root-relative paths |
| Repository boundaries | Local destinations that resolve outside the configured root |
| Exact path case | Links that pass on case-insensitive filesystems and fail on Linux |
| Durable local targets | Existing links to Git-ignored or mdrepo-excluded files |
| Rooted document graph | Pages disconnected from configured roots |
| Structured exceptions | Anonymous ignores, expired waivers, and stale policy debt |
| Conservative fixing | Ambiguous edits, overlapping replacements, and changed CRLF line endings |

Safe fixes are applied only when the source span is verified and the replacement is unambiguous.
Writes are atomic, and existing CRLF line endings are preserved.

Orphan analysis is generic Markdown graph reachability. It is not the same as membership in an
MkDocs `nav` tree; rumdl `MD074` owns that site-generator-specific check.

## Configuration

`mdrepo` searches upward for the nearest project root containing one of these markers:

1. `pyproject.toml` with a `[tool.mdrepo]` table;
2. `mdrepo.toml`;
3. `.mdrepo.toml`;
4. a `.git` entry, used only as a root fallback.

A small paired configuration is often enough:

```toml
[tool.rumdl]
flavor = "gfm"

[tool.mdrepo.orphans]
enabled = true
roots = ["README.md", "docs/index.md"]
```

The link-policy defaults are strict and portable. In the normal paired workflow,
`links.check-missing-targets` remains `false` so rumdl `MD057` is the sole authority for ordinary
missing targets. `links.check-durable-targets` remains enabled so existing links cannot silently
point at transient or excluded files.

### Structured exceptions

Exceptions are explicit policy records rather than casual ignore globs:

```toml
[tool.mdrepo.exception-policy]
report-expired = true
report-unused = true
expired-severity = "warning"
unused-severity = "warning"

[[tool.mdrepo.exceptions]]
id = "standalone-changelog"
rule = "MDR101"
path = "CHANGELOG.md"
reason = "Package metadata exposes this file independently of the documentation graph."
expires = 2027-01-01
```

`MDR201` reports expired exceptions. `MDR202` reports exceptions that no longer suppress a finding.
Unknown configuration keys are errors. Repeated `--config` overlays and typed
`--set dotted.key=value` overrides are applied last.

See the [configuration reference](docs/configuration.md) for discovery patterns, link policy, graph
resolution, rule selection, severity overrides, and configuration layering.

## Recommended workflow with rumdl

Run document formatting first, then repository-policy fixes, and finish with read-only checks:

```bash
uvx rumdl check --fix .
mdrepo fix .
uvx rumdl check .
python -m mdrepo check .
```

In CI, keep the two authorities visible and independent:

```bash
rumdl check .
python -m mdrepo check . --format github
```

A green run means the Markdown layer and repository-policy layer are clean. It does not claim that
remote websites respond or that a documentation generator can build the published site.

## CI integration

See the [CI integration guide](docs/ci-integration.md) for `mdrepo`'s standalone installation,
root and configuration contract, mutation ordering, exclusions, platform commands, exit codes,
and a minimal GitHub Actions job.

`MDR004` is available as a standalone missing-target fallback, but it remains disabled in the normal
rumdl workflow to avoid duplicate ownership and duplicate diagnostics.

## Commands

| Command | Purpose |
|---|---|
| `mdrepo check [PATH ...]` | Check repository policy without modifying files. |
| `mdrepo fix [PATH ...]` | Apply only source-verified safe fixes. |
| `mdrepo fix --dry-run` | Print proposed diffs and return `1` when edits are available. |
| `mdrepo fix --diff` | Apply fixes and also print unified diffs. |
| `mdrepo graph --graph-format FORMAT` | Render the graph as `text`, `json`, or `dot`. |
| `mdrepo rules` | List built-in rule metadata. |
| `mdrepo config` | Print the fully resolved configuration as JSON. |

Useful invocation overrides:

```bash
mdrepo check . --select MDR001,MDR005
mdrepo check . --ignore MDR101
mdrepo check . --format github
mdrepo check . --fail-on warning
mdrepo check . --set links.check-missing-targets=true
```

Exit statuses are stable:

- `0`: no visible finding meets `fail-on`;
- `1`: a visible finding meets `fail-on`, or `fix --dry-run` found applicable edits;
- `2`: configuration, invocation, discovery, parsing, or safe-fix failure.

## Built-in rules

| Rule | Purpose | Safe fix |
|---|---|---:|
| `MDR001` | Backslash in a local destination | Yes |
| `MDR002` | Machine-, protocol-, or repository-root-absolute destination | Root-relative only |
| `MDR003` | Local destination escapes the repository root | No |
| `MDR004` | Standalone missing-target fallback; disabled with rumdl | No |
| `MDR005` | Path spelling differs from exact on-disk case | Yes |
| `MDR006` | Existing local target is Git-ignored or mdrepo-excluded | No |
| `MDR100` | No configured orphan-graph root exists | No |
| `MDR101` | Markdown document is unreachable from all roots | No |
| `MDR201` | Structured exception is expired | No |
| `MDR202` | Structured exception is unused | No |

Rule IDs use the `MDR` namespace so they remain distinct from rumdl's `MD` rules.

## Automation

See the [CI integration guide](docs/ci-integration.md) for the installation pin, execution
directory, discovery and exclusion rules, mutation order, platform examples, exit codes, and a
minimal GitHub Actions job.

Use GitHub output to create native annotations. Until a package release is published, pin the
repository to a commit or tag:

```yaml
- name: Install mdrepo
  run: >-
    python -m pip install
    "git+https://github.com/sheepfling/mdrepo.git@<commit-or-tag>"

- name: Check Markdown repository policy
  run: mdrepo check . --format github
```

The repository also exports a `mdrepo` pre-commit hook. Pin a tagged release when consuming it:

```yaml
repos:
  - repo: https://github.com/sheepfling/mdrepo
    rev: <release-tag>
    hooks:
      - id: mdrepo
```

## Deliberate boundaries

`mdrepo` does not format Markdown, validate heading anchors, crawl external URLs, parse
arbitrary raw HTML links, build documentation sites, or invoke other tools. The internal
`Rule` protocol remains a small extension seam without committing the project to a public
plugin-loading system.

## Development

Run the same read-only gate used by hosted CI:

```bash
uv sync --extra dev
uv run python -m scripts.ci
```

During development, apply safe fixes first and then rerun the read-only gate:

```bash
uv run python -m scripts.ci --fix
uv run python -m scripts.ci
```

Hosted CI covers Ubuntu and Windows on Python 3.11, 3.12, 3.13, and 3.14. The gate includes compilation,
Ruff lint and formatting, branch-coverage tests, isolated sdist and wheel validation, strict
Pyright, rumdl, pre-commit validation, and an `mdrepo` self-check.

## Documentation

- [Responsibility boundary](docs/responsibility-boundary.md)
- [Configuration reference](docs/configuration.md)
- [CI integration](docs/ci-integration.md)
- [Design notes](docs/design.md)
- [Changelog](CHANGELOG.md)

`mdrepo` is released under the [MIT License](LICENSE).

[ci-badge]: https://github.com/sheepfling/mdrepo/actions/workflows/ci.yml/badge.svg?branch=main
[ci]: https://github.com/sheepfling/mdrepo/actions/workflows/ci.yml?query=branch%3Amain
[license-badge]: https://img.shields.io/badge/license-MIT-blue.svg
[license]: LICENSE
[pre-commit-badge]: https://img.shields.io/badge/pre--commit-enabled-FAB040?logo=pre-commit
[pre-commit]: .pre-commit-config.yaml
[python-badge]: https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white
[python]: https://www.python.org/downloads/
[ruff-badge]: https://img.shields.io/badge/lint-Ruff-D7FF64?logo=ruff&logoColor=261230
[ruff]: https://docs.astral.sh/ruff/
[rumdl]: https://rumdl.dev/
[typing-badge]: https://img.shields.io/badge/typing-strict%20Pyright-3178C6
[typing]: pyproject.toml
