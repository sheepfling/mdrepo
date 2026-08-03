# Markdown Repository Policy (`mdrepo`)

`mdrepo` is a small Python 3.12+ checker for repository semantics that a general Markdown linter
cannot know. It is designed to run **beside rumdl**, not replace it.

```text
rumdl   -> Is each Markdown document well formed, consistently styled, and locally resolvable?
mdrepo  -> Does the document set obey this repository's portability and navigation policy?
```

`mdrepo` begins where a decision requires repository identity, cross-platform filesystem semantics,
or the topology of the document set. It ends before Markdown formatting, dialect conformance,
heading-fragment validation, live HTTP checking, and documentation-site builds.

There is no Node or npm runtime, no live HTTP crawler, no plugin loader, and no subprocess wrapper.
The runtime dependencies are `markdown-it-py`, `pathspec`, and Pydantic.

## Responsibility split

| Concern | Authority |
|---|---|
| Markdown syntax, flavor, headings, lists, tables, fences, whitespace, and style | rumdl |
| Relative target existence and heading fragments | rumdl `MD057` and `MD051` |
| MkDocs navigation validation | rumdl `MD074` |
| POSIX local paths, repository boundaries, and exact on-disk case | `mdrepo` |
| Mutable provider URLs that point back into the same repository | `mdrepo` |
| Generic document reachability from configured roots | `mdrepo` |
| Reasoned, expiring, and stale-exception governance | `mdrepo` |
| Live external URL availability | Neither tool |
| Generated-site routes and renderer-specific semantics | The documentation build |

The tools are independent. `mdrepo` does not invoke rumdl, consume rumdl diagnostics, interpret rumdl
inline suppression comments, or forward rumdl configuration. Each command keeps its own
configuration, diagnostics, and exit status.

See [the complete responsibility boundary](docs/responsibility-boundary.md) for the overlap policy,
MkDocs distinction, guarantees, and non-goals.

## What the focused tool adds

- Rejects backslashes, machine-local absolute paths, root escapes, and non-portable path casing.
- Detects mutable GitHub, GitLab, or Bitbucket web links that point back into the current repository
  and can safely replace them with relative links.
- Treats Markdown documents as a rooted graph and reports unreachable documents when orphan checks
  are enabled.
- Uses structured exceptions with IDs, reasons, optional target patterns, and expiry dates.
- Reports expired exceptions and stale exceptions that no longer suppress anything.
- Applies only source-span-verified, non-overlapping fixes and preserves CRLF line endings.

`MDR004` can check missing local targets, but it is a standalone fallback. It remains disabled in the
normal rumdl workflow so rumdl `MD057` stays authoritative.

## Installation and first run

From the source tree:

```bash
uv sync --extra dev
uv run pytest
uv run mdrepo check .
```

As a persistent command:

```bash
uv tool install .
mdrepo check .
```

## Development and CI

Install the complete development environment and run exactly the checks used by GitHub Actions:

```bash
python -m pip install -e ".[dev]"
python scripts/ci.py
```

The runner is read-only by default. For local cleanup, `python scripts/ci.py --fix` runs Ruff,
Ruff formatting, Scope Markers, rumdl, and `mdrepo fix` in their safe-fix modes before repeating
the checks against the resulting checkout.
Scope Markers runs after ordinary Python formatting; `scripts/check_format.py` verifies Ruff on
temporary marker-free copies so the two tools remain independently replaceable.

The CI matrix covers Ubuntu and Windows on Python 3.12, 3.13, and 3.14. It checks compilation,
Ruff, formatting compatibility, tests with branch coverage reporting, isolated sdist/wheel builds
with `twine check`, strict Pyright, Scope Markers, rumdl, pre-commit configuration and hook
execution, and an `mdrepo` self-check with orphan analysis enabled.

For local enforcement, install the hook with `pre-commit install`. After publishing, other
repositories can use the `.pre-commit-hooks.yaml` definition.

### Release process

Update the version and changelog, run `python scripts/ci.py`, then push a matching `vX.Y.Z` tag.
The release workflow builds the sdist and wheel in a separate job and publishes them through the
`pypi` GitHub environment using PyPI trusted publishing. Configure that trusted publisher and add
required reviewers to the environment before enabling releases.

## Normal workflow with rumdl

Local cleanup:

```bash
uvx rumdl check --fix .
mdrepo fix .
uvx rumdl check .
mdrepo check .
```

Continuous integration:

```bash
rumdl check .
mdrepo check .
```

Rumdl runs first because it owns document normalization and ordinary linting. `mdrepo fix` then
applies only repository-policy rewrites. The final check-only commands verify the resulting tree.

A green run of both tools means the Markdown layer and repository-policy layer are clean. It does
**not** mean that external websites respond or that a documentation generator can successfully build
the site.

## Configuration

`mdrepo` searches upward for the nearest directory containing one of these:

1. `pyproject.toml` with a `[tool.mdrepo]` table;
2. `mdrepo.toml`;
3. `.mdrepo.toml`;
4. a `.git` entry, used only as a root fallback.

When multiple configuration files exist in the discovered root, they are merged in the order shown
above. Later files replace scalar values and lists while nested tables merge recursively.
Additional `--config` overlays and repeated typed `--set dotted.key=value` overrides are applied
last.

Rumdl and mdrepo can coexist in one `pyproject.toml` without sharing configuration:

```toml
[tool.rumdl]
flavor = "standard"

[tool.rumdl.MD057]
absolute-links = "ignore"

[tool.mdrepo]
include = ["*.md", "**/*.md"]
exclude = [".git/**", ".venv/**", "build/**", "dist/**", "site/**"]
fail-on = "error"
output = "text"

[tool.mdrepo.links]
require-posix = true
allow-root-relative = false
allow-outside-root = false
check-missing-targets = false # Rumdl MD057 owns ordinary target existence.
check-case = true

[tool.mdrepo.repository]
enabled = true
discover-from-git = true
remote = "origin"
relative-refs = ["main", "master"]
include-current-branch = true
require-existing-target = true

[tool.mdrepo.orphans]
enabled = true
roots = ["README.md", "docs/index.md"]
extensionless-links = true
markdown-extensions = [".md", ".markdown"]
directory-indexes = ["README.md", "index.md"]

[tool.mdrepo.rules]
ignore = []
select = []
severity = { MDR101 = "warning" }

[tool.mdrepo.exception-policy]
report-expired = true
report-unused = true
expired-severity = "warning"
unused-severity = "warning"

[[tool.mdrepo.exceptions]]
id = "standalone-changelog"
rule = "MDR101"
path = "CHANGELOG.md"
reason = "Package tooling exposes this document independently of the documentation graph."
expires = 2027-01-01
```

A repository URL may be supplied explicitly when Git metadata is unavailable:

```toml
[tool.mdrepo.repository]
url = "https://github.com/owner/project"
discover-from-git = false
provider = "github"
relative-refs = ["main"]
```

Only configured mutable refs are converted. Commit-pinned links, provider line anchors such as
`#L10`, and URLs with query strings are intentionally left alone because a relative Markdown link
would not preserve their semantics.

## Commands

```bash
mdrepo check [PATH ...]
mdrepo fix [PATH ...]
mdrepo fix --dry-run
mdrepo fix --diff
mdrepo graph --graph-format text
mdrepo graph --graph-format json
mdrepo graph --graph-format dot
mdrepo rules
mdrepo config
```

Useful invocation overrides:

```bash
mdrepo check . --set links.check-missing-targets=true
mdrepo check . --select MDR001,MDR005,MDR006
mdrepo check . --ignore MDR101
mdrepo check . --format github
mdrepo check . --fail-on warning
```

Exit statuses are stable:

- `0`: no visible finding meets `fail-on`;
- `1`: at least one visible finding meets `fail-on`, or `fix --dry-run` found applicable edits;
- `2`: configuration, invocation, file-discovery, parsing, or safe-fix failure.

## Built-in rules

| Rule | Purpose | Safe fix |
|---|---|---:|
| `MDR001` | Backslash in a local destination | Yes |
| `MDR002` | Machine-, protocol-, or repository-root-absolute destination | Root-relative only |
| `MDR003` | Local destination escapes the repository root | No |
| `MDR004` | Standalone missing-target fallback; disabled with rumdl | No |
| `MDR005` | Path spelling differs from exact on-disk case | Yes |
| `MDR006` | Mutable web URL points back into this repository | Yes |
| `MDR100` | No configured orphan-graph root exists | No |
| `MDR101` | Markdown document is unreachable from all roots | No |
| `MDR201` | Structured exception is expired | No |
| `MDR202` | Structured exception is unused | No |

## Deliberate boundaries

`mdrepo` does not format tables, headings, fences, lists, or whitespace. It does not generate or
validate heading anchors. It does not check whether an external website currently responds. It does
not parse links embedded in arbitrary raw HTML. It does not validate a site generator's build
output. It does not expose a public plugin-discovery mechanism.

The internal `Rule` protocol remains a small extension seam, so a real second rule package can be
added later without first maintaining pytest-style hook loading, hook ordering, CLI injection, or
plugin-specific configuration merging.

See [the responsibility boundary](docs/responsibility-boundary.md),
[design notes](docs/design.md), [configuration reference](docs/configuration.md),
[migration notes from the 0.1 prototype](docs/migration-from-0.1.md),
[validation record](VALIDATION.md), and [project changelog](CHANGELOG.md).
