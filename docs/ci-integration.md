# CI integration

This guide documents `mdrepo` as a standalone repository-policy check. It does not require,
invoke, or configure another formatter or repository tool.

This repository is itself a working integration example: its `pyproject.toml` contains independent
`[tool.rumdl]` and `[tool.mdrepo]` tables, its pre-commit files show both hook modes, and its
GitHub Actions workflow runs the same provider-neutral validation runner used locally.

The important integration rule is sequencing: run formatters, tests, and generated-artifact steps
first, then run the final read-only checks from the repository root:

This repository enables rumdl `MD029` with `style = "ordered"` and rumdl `MD060` with
`style = "aligned"` in `pyproject.toml`. The local pre-commit hook runs rumdl with `--fix`, and
the CI runner's `--fix` mode applies the same step before its read-only checks.

```bash
rumdl check --fix .
python -m mdrepo fix .
python -m pytest
# build and validate generated artifacts, if applicable
rumdl check .
python -m mdrepo check .
```

`python -m mdrepo check .` is repository-root and configuration sensitive. Running it from a
subdirectory, before generated files are produced, or before formatters finish can validate a
different tree or configuration than the one CI ultimately publishes.

## Installation

Pin `mdrepo` in the consuming project's development dependencies:

```toml
[project.optional-dependencies]
dev = [
    "mdrepo==0.0.1a2",
    "rumdl>=0.2.49,<0.3",
]
```

Install it into the interpreter used by CI:

```bash
python -m pip install -e ".[dev]"
```

## Invocation contract

Run from the repository root. The reliable cross-platform command is:

```bash
python -m mdrepo check .
```

The check is read-only. `mdrepo fix .` may modify Markdown files, while `mdrepo fix . --dry-run`
does not write files and returns `1` when fixes are available.

The command returns:

- `0` when no visible finding meets `fail-on`;
- `1` when a visible finding meets `fail-on`;
- `2` for configuration, invocation, discovery, parsing, or safe-fix failures.

The module command works identically in Windows PowerShell, macOS shells, and Linux shells. Using
`python -m` selects the interpreter that owns the installed package and avoids dependence on a
globally discoverable executable:

```powershell
# Windows PowerShell
python -m mdrepo check .
```

```bash
# macOS or Linux
python3 -m mdrepo check .
```

## Configuration and discovery

`mdrepo` searches upward from the working directory for the nearest supported project marker:

1. `pyproject.toml` containing `[tool.mdrepo]`;
2. `mdrepo.toml`;
3. `.mdrepo.toml`;
4. a `.git` entry as a root fallback.

An explicit `--config` file is an additional overlay and does not change the discovered project
root. Use `--root` when intentionally selecting another repository.

`mdrepo` performs four distinct operations:

1. **Markdown discovery** selects regular, non-symlink Markdown files using `include` and `exclude`.
2. **Link-target validation** checks local destinations for portability, repository boundaries, and
   optionally missing targets.
3. **Case-sensitivity checks** compare local path spelling with the exact on-disk spelling.
4. **Orphan detection** optionally builds a document graph from configured `orphans.roots` and
   reports documents unreachable from those entry points.

For a notes repository, make the scope explicit. The rumdl and mdrepo tables can live together in
the same `pyproject.toml`, but each tool reads only its own table:

```toml
[tool.rumdl]
line-length = 100

[tool.rumdl.MD013]
line-length = 100

[tool.mdrepo]
include = ["*.md", "**/*.md"]
respect-gitignore = true
exclude = [
    "inbox/**",
    "artifacts/**",
    "build/**",
    "dist/**",
    ".venv*/**",
    ".pytest_cache/**",
    ".ruff_cache/**",
]

[tool.mdrepo.links]
check-missing-targets = false
check-case = true

[tool.mdrepo.orphans]
enabled = false
```

This keeps link and case policy enabled while deferring orphan cleanup for historical content.
Enable orphan detection after choosing deliberate entry documents:

```toml
[tool.mdrepo.orphans]
enabled = true
roots = ["README.md", "docs/index.md"]
```

Markdown discovery respects `.gitignore` by default in addition to `include` and `exclude`. Set
`respect-gitignore = false` only when generated, scratch, vendor, or legacy Markdown must be
inspected explicitly. With durable-target checking enabled, `MDR006` separately reads applicable
repository `.gitignore` files and reports existing links to ignored targets. When orphan analysis
is enabled, Git-ignored Markdown documents are omitted from the graph so they cannot create
reachability or orphan noise. Explicit file and directory selections remain constrained by the
resolved `include`/`exclude` policy. Symlinks are not admitted to the discovered document set.

## Pre-commit integration

For a repository that installs `mdrepo` into its development environment, use a local system hook:

```yaml
repos:
  - repo: local
    hooks:
      - id: mdrepo
        name: mdrepo repository policy
        entry: python -m mdrepo check .
        language: system
        types: [markdown]
        pass_filenames: false
```

The hook is read-only. It runs from the repository root, checks the complete configured document
set, and returns a nonzero status for policy findings or configuration failures. `pre-commit`
passes the selected interpreter environment to the hook; install `mdrepo` into that same
environment. Do not configure both the published and local forms in the same repository.

## GitHub Actions

This minimal job runs from the checkout root and uses the same interpreter for installation and
validation:

```yaml
name: Markdown repository policy

on:
  push:
  pull_request:

jobs:
  mdrepo:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m pip install --upgrade pip
      - run: python -m pip install -e ".[dev]"
      - run: rumdl check .
      - run: python -m mdrepo check .
```

Keep the working directory at the checkout root unless `--root` intentionally selects another
repository. Add the project's own formatter, test, and documentation-linter steps before the final
`mdrepo` command; `mdrepo` neither invokes nor depends on them.
