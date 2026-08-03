# Design

## Purpose

The tool owns only policy that requires repository context. Rumdl remains the Markdown linter,
formatter, ordinary local-target checker, and heading-fragment validator. Live HTTP status and
rendered-site correctness are explicitly outside the scope.

The durable boundary is:

```text
Document semantics and presentation  -> rumdl
Repository identity and topology     -> mdrepo
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
4. Record direct destinations, autolinks, reference uses, and reference definitions separately.
5. Resolve selected documents' policy destinations against the repository filesystem.
6. Discover the local Git web identity when same-repository checks are enabled.
7. Build the complete document graph when orphan analysis or graph output is requested.
8. Run the fixed built-in rule registry.
9. Apply structured exceptions and produce exception-health diagnostics.
10. Render text, JSON, or GitHub Actions diagnostics.

No network request or subprocess invocation of another checker occurs in this flow. The only
subprocess use is bounded, read-only local Git metadata discovery.

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

## Same-repository conversion

Repository identity is read from explicit configuration or `git config --get remote.<name>.url`.
HTTPS, SSH, and SCP-style Git remotes are normalized to a web base. Supported file routes are:

- GitHub: `/blob/<ref>/<path>` and `raw.githubusercontent.com`;
- GitLab: `/-/blob/<ref>/<path>`;
- Bitbucket: `/src/<ref>/<path>`.

A route is eligible only when its ref is in the configured/discovered mutable-ref set. Provider line
anchors and query strings are skipped because conversion would not be semantically equivalent.

## Graph scope

The document graph is repository-wide even when `check` receives path filters. Link diagnostics are
limited to selected files, but an enabled orphan rule remains a repository property. Unused
exceptions are reported only during a full, unfiltered check so partial runs do not create false
staleness findings.

The graph is generic Markdown reachability. It is not a replacement for a documentation generator's
navigation model. In a MkDocs project, rumdl `MD074` can validate `mkdocs.yml` membership while
`MDR101` independently checks prose-link reachability; enable both only when both properties matter.

## Extension seam

The package has a typed `Rule` protocol and a deterministic built-in rule tuple. It deliberately has
no entry-point loading or lifecycle hooks. A plugin system should be added only after at least two
independently distributed rule packages establish the required API from real use.

A proposed rule belongs here only when it requires repository context. A rule about Markdown style,
syntax, flavor behavior, headings, fragments, or ordinary target existence should be proposed to
rumdl or handled through rumdl configuration instead.

## Capability retirement

When rumdl or a documentation generator fully assumes one of the `mdrepo` tool's responsibilities,
the corresponding `mdrepo` rule should be deprecated rather than maintained as a competing
implementation.
The package remains valuable by staying narrow, not by accumulating every Markdown-related check.
