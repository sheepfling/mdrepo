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

For a Python project, add both packages to its development dependencies. The following is the
released-package baseline shown in the CI examples:

```toml
[project.optional-dependencies]
dev = [
    "mdrepo==0.0.1",
    "rumdl>=0.2.49,<0.3",
]
```

Install the development extra in the project's existing environment:

```bash
python -m pip install -e ".[dev]"
```

The `mdrepo==0.0.1` release requires Python 3.11 or newer. Use Python 3.11 or newer when
installing that pin. If you are testing an unreleased source checkout with Python 3.10, install
that checkout and confirm its metadata supports the selected interpreter.

## 3. Create or review mdrepo configuration

From the repository root, run:

```bash
mdrepo init --orphan-root README.md --orphan-root docs/index.md
```

Pass only entry documents that exist and should anchor the documentation graph. Omit an entry
point you do not use. `mdrepo init` creates `mdrepo.toml` without editing `pyproject.toml`; it
refuses to overwrite an existing mdrepo configuration. If your repository already has
`[tool.mdrepo]`, edit that existing configuration instead.

Review the generated `include` and `respect-gitignore` settings against the repository. Add an
`exclude` list for Markdown that should not be checked. Orphan detection stays disabled unless you
pass one or more `--orphan-root` options.

By default, `mdrepo` leaves missing-file and heading-fragment checks disabled so rumdl can own
those checks through `MD057` and `MD051`. If you are not using rumdl and want mdrepo's missing
local-target checks, initialize with:

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
