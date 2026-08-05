# Design

## Purpose

The tool owns only policy that requires repository context. Rumdl remains the Markdown linter,
formatter, ordinary local-target checker, and heading-fragment validator. Live HTTP status and
rendered-site correctness are explicitly outside the scope.

The durable boundary is:

```text
Document semantics and presentation  -> rumdl
Repository filesystem and topology   -> mdrepo
Network and generated-site behavior  -> other tools
```

See [the responsibility boundary](responsibility-boundary.md) for the authority matrix and canonical
paired workflow.

## Independence from rumdl

`mdrepo` deliberately does not:

- execute or wrap rumdl;
- parse rumdl output;
- import rumdl as a library;
- translate rumdl configuration;
- honor rumdl inline disable comments;
- duplicate rumdl formatting or fragment-generation behavior.

The tools can share a `pyproject.toml`, but their tables and rule namespaces remain independent. This
keeps upgrades isolated and makes every failure attributable to one layer.

The only intentional overlap is optional `MDR004`, a standalone missing-target fallback. It is
disabled by default and should stay disabled when rumdl `MD057` runs.

## Data flow

1. Discover the repository root and merge typed TOML configuration.
2. Collect the complete configured Markdown document set.
3. Parse each document with `markdown-it-py`.
4. Record direct destinations, `autolinks`, reference uses, and reference definitions separately.
5. Resolve selected documents' policy destinations against the repository filesystem.
6. Classify existing local targets against `.gitignore` and mdrepo exclusion policy.
7. Build the durable document graph when orphan analysis or graph output is requested; Git-ignored
   documents are omitted from its nodes and edges.
8. Run the fixed built-in rule registry.
9. Apply structured exceptions and produce exception-health diagnostics.
10. Render text, JSON, or GitHub Actions diagnostics.

No network request or subprocess invocation of another checker occurs in this flow.

## Filesystem input-safety invariant

Filesystem discovery is a trust boundary. A path is eligible for parsing, graph construction, safe
fixes, or artifact validation only when it is a regular file; repository Markdown candidates and
release artifacts must also be non-symlinks. Recursive directory scans can report named pipes,
sockets, devices, and other filesystem entries whose names match an include pattern; those entries
must be rejected before any code calls `read_bytes()` or otherwise opens them. Explicit path
selection must continue to select from the same validated project-file set, and configuration paths
must be checked before TOML is read.

Every change to file discovery or path selection must preserve this invariant with a regression
test for non-regular entries. Use a real FIFO test on platforms that support `os.mkfifo` and a
cross-platform simulated candidate test elsewhere.

## Why reference definitions are checked once

A reference destination belongs to its definition rather than each use site. Reporting and fixing
that definition once prevents duplicate findings and makes the source edit exact:

```markdown
[First][guide]
[Second][guide]

[guide]: docs/guide.md
```

The graph still follows both semantic uses.

## Safe-fix contract

A fix includes:

- an absolute file path;
- a half-open character span;
- the exact source text expected at that span;
- the replacement text;
- a short description.

Fixes are de-duplicated, checked for overlap, applied from the end of each file toward the beginning,
and rejected if the source no longer matches. Each modified file is written atomically in its own
directory while preserving its permission mode and original line-ending bytes.

`mdrepo fix` changes only destination spans for rules with a semantically equivalent replacement. It
does not reflow, restyle, or otherwise format Markdown; that remains rumdl's responsibility.

## Graph scope

The document graph is repository-wide even when `check` receives path filters. File-level
diagnostics and fixes are limited to selected files: link rules consume `selected_documents` via
`policy_links`, and orphan diagnostics consume `selected_documents` while testing reachability
against the complete graph. Configuration-level diagnostics may still apply to the repository as
a whole. Unused exceptions are reported only during a full, unfiltered check so partial runs do
not create false staleness findings.

This is the scope invariant for built-in rules:

- `documents` is the complete parsed repository and is reserved for graph-wide context;
- `selected_documents` is the invocation's diagnostic scope;
- `policy_links` contains only destinations from selected documents;
- `graph` is built from all documents so links crossing a path filter remain resolvable.

The graph is generic Markdown reachability. It is not a replacement for a documentation generator's
navigation model. In a MkDocs project, rumdl `MD074` can validate `mkdocs.yml` membership while
`MDR101` independently checks prose-link reachability; enable both only when both properties matter.

## Public import boundary

The supported consumer interface is the `mdrepo` console command, its `python -m mdrepo`
equivalent, and the focused Git-ignore API exported from the package root:
`mdrepo.is_gitignored(root, target)`, `mdrepo.GitIgnorePolicy`,
`mdrepo.GitIgnoreWalker`, `mdrepo.GitIgnoreDecision`, and `mdrepo.GitIgnoreError`.
Modules such as `config`, `engine`, `markdown`, `resolution`, and `rules` are implementation
modules rather than stable programmatic APIs.

## Extension seam

The package has a typed `Rule` protocol and a deterministic built-in rule tuple. It deliberately has
no entry-point loading or lifecycle hooks. A plugin system should be added only after at least two
independently distributed rule packages establish the required API from real use.

## Versioning and release artifacts

The package version is derived by `setuptools-scm` from Git tags. `pyproject.toml` deliberately does
not contain a manually maintained `project.version`, and runtime `mdrepo.__version__` reads the
installed distribution metadata. Release tags use the `vX.Y.Z` form.

Before building a release, install the development environment and verify the tag through the
provider-neutral release helper:

```bash
RELEASE_TAG=vX.Y.Z python -m scripts.release build
python -m twine upload dist/*
```

On PowerShell, use `$env:RELEASE_TAG = "vX.Y.Z"` instead. The build helper clears stale wheel and
sdist artifacts, builds both products through the PEP 517 backend, validates them with `twine`, and
returns only the artifacts produced by the current build.

A proposed rule belongs here only when it requires repository context. A rule about Markdown style,
syntax, flavor behavior, headings, fragments, or ordinary target existence should be proposed to
rumdl or handled through rumdl configuration instead.

## Capability retirement

When rumdl or a documentation generator fully assumes one of the `mdrepo` tool's responsibilities,
the corresponding `mdrepo` rule should be deprecated rather than maintained as a competing
implementation.
The package remains valuable by staying narrow, not by accumulating every Markdown-related check.
