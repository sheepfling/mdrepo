# Configuration reference

All models are strict: unknown keys are errors. TOML uses kebab-case names, while repeated
`--set` overrides accept either kebab-case or underscore spelling in dotted keys.

## Paired configuration with rumdl

Rumdl and mdrepo may use the same `pyproject.toml`, but neither reads the other's table:

```toml
[tool.rumdl]
flavor = "standard"

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

## Top-level keys

| Key        | Default                          | Meaning                            |
|------------|----------------------------------|------------------------------------|
| `include`  | `*.md`, `**/*.md`                | Gitignore-style inclusion patterns |
| `exclude`  | common build and VCS directories | Gitignore-style exclusion patterns |
| `encoding` | `utf-8`                          | Markdown source encoding           |
| `output`   | `text`                           | `text`, `json`, or `github`        |
| `fail-on`  | `error`                          | `info`, `warning`, or `error`      |

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

This is generic Markdown graph reachability. It is not a site-generator navigation validator. For
MkDocs, rumdl `MD074` can separately check the `mkdocs.yml` navigation and omitted files.

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

Nested tables merge. Scalar values and lists replace earlier values.
