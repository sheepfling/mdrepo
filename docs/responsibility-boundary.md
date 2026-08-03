# Responsibility boundary: `rumdl` and `mdrepo`

## The contract in one sentence

`rumdl` validates and formats Markdown **as a document format**. `mdrepo` validates Markdown
references **as relationships inside a repository**.

A third category, live network reachability, belongs to neither tool in this focused workflow.

```text
Markdown document correctness          Repository relationship correctness
──────────────────────────────          ───────────────────────────────────
rumdl                                   mdrepo

syntax and structure                    portable local path policy
formatting and ordinary lint rules      exact on-disk path spelling
local target existence                  rooted document reachability
heading-fragment validity               rooted document reachability
Markdown flavor behavior                governed exception lifecycle

                         Live HTTP reachability
                         ──────────────────────
                         deliberately not checked
```

## Ownership rule

A proposed feature belongs in `rumdl` when it can be decided from Markdown syntax, a Markdown
flavor, a target file, or a target heading without knowing the repository's filesystem policy.

A proposed feature belongs in `mdrepo` only when it needs one or more of these:

- the repository root;
- operating-system-independent path semantics;
- relationships among multiple Markdown documents;
- a rooted documentation graph;
- the lifecycle of a documented repository-policy exception.

A proposed feature belongs in neither tool when it requires an HTTP request, login, redirect
policy, retry policy, or interpretation of a remote server response.

## Responsibility matrix

| Concern                                                                | Owner                                         | Reason                                                                       |
|------------------------------------------------------------------------|-----------------------------------------------|------------------------------------------------------------------------------|
| Heading, list, table, fence, and whitespace formatting                 | `rumdl`                                       | General Markdown formatting does not require repository semantics.           |
| Markdown syntax and structural linting                                 | `rumdl`                                       | These are document-level rules.                                              |
| Heading hierarchy, alt text, empty links, and similar lint rules       | `rumdl`                                       | These are ordinary Markdown quality checks.                                  |
| Markdown flavor behavior such as GFM, MkDocs, MDX, Obsidian, or Quarto | `rumdl`                                       | Dialect parsing and flavor-aware linting are formatter/linter concerns.      |
| Relative target exists                                                 | `rumdl`                                       | `MD057` already owns ordinary local target validation.                       |
| Same-file or cross-file heading fragment exists                        | `rumdl`                                       | `MD051` already owns anchor validation.                                      |
| MkDocs `nav` entries and omitted files                                 | `rumdl` when the MkDocs nav is authoritative  | `MD074` understands the site generator's navigation model.                   |
| Local Markdown destinations use `/`, not `\\`                          | `mdrepo`                                      | This is a portability policy across operating systems.                       |
| No drive path, UNC path, home-relative path, or `file:` URL            | `mdrepo`                                      | These destinations embed one machine's filesystem assumptions.               |
| A local destination must not escape the repository root                | `mdrepo`                                      | The repository root is required to decide the rule.                          |
| Destination spelling matches exact on-disk case                        | `mdrepo`                                      | This protects Windows-authored links from failing on case-sensitive systems. |
| Existing local target is not Git-ignored or mdrepo-excluded             | `mdrepo`                                      | Existence alone does not prove that the target is durable in a checkout.     |
| Markdown page is reachable from configured documentation roots         | `mdrepo`                                      | This is a generic repository-wide graph property.                            |
| Exception has a reason, is unexpired, and still suppresses something   | `mdrepo`                                      | This is repository-policy governance rather than Markdown linting.           |
| External website currently responds                                    | Neither                                       | The focused toolchain intentionally performs no network crawl.               |
| Arbitrary raw HTML `href` or `src` semantics                           | Neither in the current release                | `mdrepo` limits itself to parsed Markdown destinations.                      |
| Generated site routes and runtime-generated pages                      | Site generator or project-specific validation | Source-tree existence is not enough to prove generated-site validity.        |

## Intentional overlap controls

### Missing local targets

The normal combined workflow leaves `mdrepo`'s `MDR004` disabled:

```toml
[tool.mdrepo.links]
check-missing-targets = false
```

Rumdl then owns missing relative files through `MD057`, and heading fragments through `MD051`.
`MDR004` is only a standalone fallback for a repository that deliberately runs `mdrepo` without
rumdl. It is not part of the recommended two-tool profile.

### Repository-root-relative links

Rumdl's `MD057` ignores absolute-style links by default because `/guide/` may be a valid published
site route. `mdrepo` may still reject `/docs/guide.md` as a repository portability policy.

Choose the model deliberately:

- Source-tree-relative policy: leave rumdl's absolute-link handling at its default and let
  `mdrepo` reject root-relative destinations.
- MkDocs site-route policy: configure rumdl to resolve absolute links relative to `docs_dir` and set
  `mdrepo.links.allow-root-relative = true`.

Do not configure both tools to report the same root-relative link unless duplicate diagnostics are
intentional.

### Orphan pages and MkDocs navigation

There are two legitimate definitions of an orphan:

1. A page omitted from an authoritative MkDocs `nav` tree.
2. A page unreachable through Markdown links from configured repository roots.

Use rumdl `MD074` for the first definition. Use `mdrepo` `MDR101` for the second. In a MkDocs
repository, select the definition that represents publication policy, or run both only when both
properties matter.

### Fixes

Rumdl owns Markdown formatting and general lint fixes. `mdrepo` fixes only repository destinations
when the replacement is unambiguous and source-span verified.

The recommended edit loop is:

```bash
uvx rumdl check --fix .
mdrepo fix .
uvx rumdl check .
mdrepo check .
```

Running rumdl first gives `mdrepo` normalized, parseable Markdown. The final two checks prove that
neither tool left an unresolved diagnostic.

## How the tools cooperate

The tools do not invoke one another and do not share an internal API. They cooperate through the
repository contents and independent configuration tables.

### Rumdl pass

Rumdl parses each document according to the selected Markdown flavor, applies formatting and
ordinary lint rules, checks local file targets, and validates heading fragments.

### `mdrepo` pass

`mdrepo` then:

1. discovers the repository root and resolves typed configuration;
2. discovers the configured Markdown document set, admitting only regular non-symlink files;
3. parses Markdown link destinations and reference definitions;
4. resolves local destinations against the repository filesystem;
5. applies portable-path and exact-case policy;
6. optionally constructs the rooted documentation graph;
7. applies structured exceptions and reports their health;
8. emits text, JSON, or GitHub Actions diagnostics.

No step performs a network request.

## Recommended configurations

### Normal GFM repository

```toml
[tool.rumdl]
flavor = "gfm"

[tool.mdrepo.links]
require-posix = true
allow-root-relative = false
allow-outside-root = false
check-missing-targets = false
check-case = true

[tool.mdrepo.orphans]
enabled = true
roots = ["README.md", "docs/index.md"]
```

### MkDocs repository with `nav` as the publication authority

Let rumdl validate the MkDocs navigation tree and leave generic graph reachability off:

```toml
[tool.rumdl]
flavor = "mkdocs"

[tool.rumdl.MD057]
absolute-links = "relative_to_docs"

[tool.rumdl.MD074]
not-found = "warn"
omitted-files = "warn"

[tool.mdrepo.links]
allow-root-relative = true
check-missing-targets = false

[tool.mdrepo.orphans]
enabled = false
```

The exact rumdl table shape should follow the installed rumdl version's configuration reference.
The ownership decision remains the same even if configuration syntax evolves.

## CI contract

CI should run both checks independently so ownership remains visible:

```bash
uvx rumdl check .
uv run mdrepo check .
```

A failure from rumdl means the Markdown document or an ordinary Markdown reference is invalid. A
failure from `mdrepo` means the repository's durability, portability, reachability, or exception
policy is invalid.

## Explicit non-goals for `mdrepo`

`mdrepo` will not become:

- a general Markdown formatter;
- a replacement for markdownlint-compatible rules;
- a Markdown flavor engine;
- a live URL checker;
- a documentation-site builder;
- a generic subprocess orchestrator;
- a public plugin platform without independently distributed rule packages that prove the need.

## Feature-admission test

Before adding a rule, ask these questions in order:

1. Can rumdl already express it directly or through a flavor-specific rule?
2. Can it be decided without repository root or a multi-document graph?
3. Does it require network access or build-system execution?
4. Is the result deterministic from the checked-out repository?

Add the rule to `mdrepo` only when the answers are **no, no, no, yes**.
