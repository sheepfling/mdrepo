# Configuration reference

All models are strict: unknown keys are errors. TOML uses kebab-case names, while repeated
`--set` overrides accept either kebab-case or underscore spelling in dotted keys.

## Paired configuration with rumdl

Rumdl and mdrepo may use the same `pyproject.toml`, but neither reads the other's table:

```toml
[tool.rumdl]
flavor = "standard"
extend-enable = ["MD029", "MD060"]

[tool.rumdl.MD029]
style = "ordered"

[tool.rumdl.MD060]
style = "aligned"

[tool.rumdl.MD057]
absolute-links = "ignore"

[tool.mdrepo.links]
require-posix = true
allow-root-relative = false
allow-outside-root = false
check-missing-targets = false
check-case = true
check-durable-targets = true
```

Keep `check-missing-targets = false` when rumdl runs. Rumdl `MD057` owns ordinary local-target
existence, and rumdl `MD051` owns heading fragments. `MDR004` exists only as a standalone fallback.

Rumdl inline suppression comments have no effect on mdrepo. Repository-policy exceptions must be
recorded through `[[tool.mdrepo.exceptions]]` with an ID and reason. See
[the responsibility boundary](responsibility-boundary.md) for the complete ownership matrix.

## Programmatic Git-ignore checks

The durable Git-ignore evaluator is also available as the small top-level Python API:

```python
from mdrepo import GitIgnorePolicy, GitIgnoreWalker, is_gitignored

if is_gitignored("/path/to/repository", "artifacts/release.md"):
    print("target is not durable in a clean checkout")

policy = GitIgnorePolicy("/path/to/repository", initial_excludes=("build/**",))
walker = GitIgnoreWalker("/path/to/repository", policy=policy)
for directory, _, filenames in walker.walk(ignored=False):
    print(directory, filenames)
```

The target may be a string, `Path`, or other path-like object. Relative targets are interpreted
relative to the repository root; targets outside that root raise `ValueError`. Invalid or unreadable
ignore files raise `mdrepo.GitIgnoreError`, allowing callers to distinguish a policy failure from a
normal non-ignored result. Use `GitIgnorePolicy` when checking multiple paths and
`GitIgnoreWalker` when walking the tree;
its `initial_excludes` argument accepts caller-owned baseline patterns. Other `mdrepo` modules
remain internal and are not part of the stable import surface.

Use `GitIgnorePolicy.explain()` when policy provenance is needed, and
`GitIgnoreWalker.iter_files()` when a caller needs only safe file paths rather than
the full `os.walk`-style directory tuple.

## Top-level keys

| Key                 | Default                                                   | Meaning                                     |
| ------------------- | --------------------------------------------------------- | ------------------------------------------- |
| `include`           | `*.md`, `**/*.md`                                         | Gitignore-style inclusion patterns          |
| `respect-gitignore` | `true`                                                    | Exclude Git-ignored Markdown from discovery |
| `exclude`           | transient build, VCS, cache, and distribution directories | Gitignore-style exclusion patterns          |
| `encoding`          | `utf-8`                                                   | Markdown source encoding                    |
| `output`            | `text`                                                    | `text`, `json`, or `github`                 |
| `fail-on`           | `error`                                                   | `info`, `warning`, or `error`               |

The default `exclude` patterns are:

```toml
exclude = [
    "**/.git/**",
    "**/.venv*/**",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/.ruff_cache/**",
    "**/.mypy_cache/**",
    "**/build/**",
    "**/dist/**",
]
```

Configured `exclude` patterns extend these defaults. Their order and repetitions are preserved
because Gitignore-style negations are order-sensitive, so a project only needs to list its
additional source-scope exclusions. `.gitignore` patterns do not need to be copied into `exclude`:
mdrepo intentionally keeps discovery scope separate from Git durability. A
Git-ignored Markdown document is excluded from discovery by default and remains a valid `MDR006`
target when another durable document links to it.

Set `respect-gitignore = false` only when generated or scratch Markdown must be inspected as part
of the source set. Those files still remain outside the orphan graph, while links from durable
documents to ignored targets receive `MDR006`.

## `[links]`

`require-posix` enables `MDR001`. `allow-root-relative` permits `/docs/file.md` links.
`allow-outside-root` permits links whose resolved path leaves the repository. Both allowances are
false by default. `check-case` enables portable exact-case checks.

`check-missing-targets` enables `MDR004`. Leave it false in the normal rumdl pairing. Enable it only
when mdrepo is intentionally being used without rumdl and the reduced standalone check is preferable
to no target validation. `check-durable-targets` enables `MDR006`, which reports existing local
targets matched by applicable repository `.gitignore` files or by mdrepo's `exclude` patterns. It is
enabled by default because an existing transient target is not a durable repository link. Use a
narrow exception or explicitly disable it when generated or local-only targets are intentional.

## `[orphans]`

Orphan analysis is disabled by default. `roots` identifies entry documents. `extensionless-links`
allows `docs/guide` to resolve to `docs/guide.md`. `directory-indexes` allows a directory link to
resolve to a configured index file.

The default discovery exclusions cover `.git`, virtual environments, Python and tool caches, and
build and distribution directories. Project-specific generated sites, artifact directories, and
legacy trees should be excluded through `.gitignore` or explicit top-level `exclude` patterns.
Git-ignored Markdown files are also excluded from discovery by default and remain subject to
`MDR006` when another document links to them.

This is generic Markdown graph reachability. It is not a site-generator navigation validator. For
MkDocs, `mkdocs.yml` is the site configuration file and its `nav` section is the publication
membership/order authority. Rumdl `MD074` can check that navigation and omitted files. If that is
the only discoverability policy, disable mdrepo orphan analysis; enable both only when both
properties matter.

Do not place casual ignore globs here. Use documented `[[exceptions]]` records for intentionally
standalone documents.

## `[rules]`

`select` is an allowlist. An empty list selects all built-in rules. `ignore` is applied after
selection. `severity` maps exact rule IDs to `info`, `warning`, or `error`.

Rule IDs use the `MDR` namespace so they cannot be confused with rumdl's `MD` namespace.

## `[[exceptions]]`

Each exception requires:

- a unique `id`;
- one exact `rule` ID;
- a Gitignore-style `path` pattern, defaulting to `**`;
- a durable `reason` of at least eight characters.

`target` optionally narrows link findings with a shell-style glob. `expires` is an optional TOML date.
Expired exceptions do not suppress their matching issue. `MDR201` and `MDR202` cannot themselves be
excepted.

These records govern mdrepo only. Use rumdl's own configuration or inline controls for rumdl rules.

## Layering example

```bash
mdrepo check . \
  --config team-policy.toml \
  --config workstation-policy.toml \
  --set rules.severity.MDR101='"warning"' \
  --set links.check-missing-targets=true
```

Nested tables merge. Scalar values and most lists replace earlier values; `exclude` extends the
built-in baseline while preserving Gitignore-style ordering and repetitions.
