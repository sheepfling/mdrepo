# Adopting rumdl and mdrepo

Use this guide to add Markdown checks to an existing repository while preserving its current
configuration and CI structure. `rumdl` checks Markdown documents; `mdrepo` checks local links,
repository paths, and reachability across the documentation set. Keep each tool's configuration
and CI command explicit.

## 1. Inspect the repository

Before changing files, identify:

- the Markdown directories that should be checked and any generated, vendored, or archived content
  to exclude;
- the documentation entry points readers should be able to reach, such as `README.md` or
  `docs/index.md`;
- existing rumdl, Markdown, Python dependency, pre-commit, and CI configuration;
- the Python version already used by the project's CI.

Do not replace existing lint or CI configuration wholesale. Add these tools to the project's
existing development environment and quality job where practical.

## 2. Install both tools

Declare both tools in the consuming project's existing development dependency group in
`pyproject.toml`. Keep version constraints there, aligned with the Python versions the project
supports and its normal dependency-update policy. For a PEP 621 project, the entries look like:

```toml
[project.optional-dependencies]
dev = [
    "mdrepo",
    "rumdl",
]
```

If the project already has a `dev` extra, add the tools to that list instead of replacing it.
Resolve or update the project's lockfile with its package manager, then install the project extra
in the local environment:

```bash
python -m pip install -e ".[dev]"
```

Use the corresponding sync or install command for projects managed by uv, Poetry, or another
package manager. CI should install the same project dependency set and honor the project's lockfile
policy rather than duplicating tool versions in workflow files.

Check that the selected `mdrepo` build supports every Python version in the project's CI matrix.
Package metadata enforces `Requires-Python`; if no published build matches, use the source checkout
being evaluated or wait for a compatible release instead of bypassing that requirement. The
`init` command is also available only in builds that include it.

## 3. Create or review mdrepo configuration

From the repository root, run this command when the installed build provides `init`:

```bash
mdrepo init --orphan-root README.md --orphan-root docs/index.md
```

Pass only entry documents that exist and should anchor the documentation graph. Omit an entry
point you do not use. `mdrepo init` creates `mdrepo.toml` without editing `pyproject.toml`; it
refuses to overwrite an existing mdrepo configuration. If your repository already has
`[tool.mdrepo]`, edit that existing configuration instead.

If your installed build predates `init`, create `mdrepo.toml` manually with the equivalent
settings:

```toml
include = ["*.md", "**/*.md"]
respect-gitignore = true

[links]
check-missing-targets = false

[orphans]
enabled = true
roots = ["README.md", "docs/index.md"]
```

Use only entry paths that exist in your repository. This starter leaves missing-target checks to
rumdl, like the `mdrepo init` default.

Review the `include` and `respect-gitignore` settings against the repository. Add an `exclude` list
for Markdown that should not be checked. The `mdrepo init` default leaves orphan detection disabled
unless you pass one or more `--orphan-root` options. The manual example above enables it because it
sets `enabled = true` and supplies roots; set it to `false` if you want to defer graph checks.

By default, `mdrepo` leaves missing-file and heading-fragment checks disabled so rumdl can own
those checks through `MD057` and `MD051`. If you are not using rumdl and want mdrepo's missing
local-target checks, set `check-missing-targets = true` in the `[links]` table of `mdrepo.toml`.
When the installed build provides `init`, the command-line equivalent is:

```bash
mdrepo init --standalone
```

For example, `mdrepo init --standalone --orphan-root README.md` enables both standalone
missing-target checks and orphan detection rooted at `README.md`.

Configure rumdl in its own supported config file, commonly `pyproject.toml`:

```toml
[tool.rumdl]
line-length = 100
```

`mdrepo init` deliberately does not edit rumdl settings or merge text into an existing project
file. See the [configuration guide](configuration.md) for mdrepo options and scope behavior.

## 4. Run checks locally

First apply any formatters or safe fixes, then run both checks read-only from the repository root:

```bash
rumdl check --fix .
mdrepo fix .
rumdl check .
python -m mdrepo check .
```

Review and commit any resulting Markdown changes and the configuration. A clean local run should
use the same dependency versions and project root as CI.

## 5. Add both checks to CI

Add the install step to the existing environment setup and run both commands after file generation,
formatting, and tests. Keep them as separate steps so CI reports which policy failed. The
[CI integration guide](ci-integration.md) provides examples for GitHub Actions, GitLab CI, and
Azure Pipelines, plus the shared command and ordering contract.
