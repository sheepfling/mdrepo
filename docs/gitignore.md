# Git-ignore integration

`mdrepo` delegates Git-ignore parsing, matching, and safe traversal to
[`gitignore-walk`](https://pypi.org/project/gitignore-walk/). Its portable evaluator checks whether
a local target is excluded by the applicable ignore policy without invoking the `git` executable.
It also works in minimal CI images and embedded Python workflows.

## Python API

The supported API is exported from the focused `mdrepo.gitignore` submodule:

```python
from mdrepo.gitignore import (
    GitIgnoreDecision,
    GitIgnoreError,
    GitIgnorePolicy,
    GitIgnoreWalker,
    is_gitignored,
)

try:
    ignored = is_gitignored("/workspace/project", "artifacts/release.md")
except GitIgnoreError as error:
    raise RuntimeError("repository ignore policy could not be evaluated") from error
```

For repeated checks or repository traversal, initialize the engine once. Its `walk()` method uses
an `os.walk`-style result and can filter to ignored or unignored entries. With `ignored=True`, it
returns only ignored child names but still traverses safe unignored directories so nested ignored
entries are discoverable. Initial exclusions are applied as the caller's baseline policy:

```python
policy = GitIgnorePolicy(
    "/workspace/project",
    initial_excludes=("build/**", "dist/**"),
)
walker = GitIgnoreWalker("/workspace/project", policy=policy)

for directory, dir_names, filenames in walker.walk(ignored=False):
    for filename in filenames:
        print(directory / filename)
```

The walk omits symlinks and special files. `follow_links=True` is rejected to preserve the same
input-safety boundary used by Markdown discovery.

Use `iter_files()` when directory names and pruning controls are not needed:

```python
for path in walker.iter_files(ignored=False):
    print(path)
```

The root and target accept strings, `Path` objects, and other path-like values. A relative target
is interpreted below the root. Targets outside the root and non-directory roots raise
`ValueError`. Missing targets are supported; an ignored ancestor still makes a missing descendant
non-durable. Invalid or unreadable ignore files raise `GitIgnoreError`.

For multiple targets, `policy.is_ignored_many(targets)` returns a tuple in input order while
sharing one ignore-policy snapshot. Use this for a repository-wide operation such as graph
eligibility filtering; a later batch starts fresh and sees updated ignore files.

Use the policy's `explain()` when a boolean result is not enough:

```python
    decision: GitIgnoreDecision = policy.explain("artifacts/release.md")
if decision.ignored:
    print(decision.source, decision.line, decision.pattern)
```

An unmatched target has `ignored=False` and no source, pattern, or line. For an ignored descendant
whose parent cannot be re-included, the explanation identifies the parent pattern that prevents
Git from traversing to the descendant.

## Semantics

Pattern parsing and matching follow Git's documented `gitignore` pattern format, including
comments, escaped leading `#` and `!`, trailing-space handling, directory-only patterns, anchored
patterns, shell globs, and the three special `**` forms. See the
[Git `gitignore` documentation](https://git-scm.com/docs/gitignore) for the normative pattern
definition.

The evaluator applies repository `.gitignore` files in order from the root toward the target:

- root and nested `.gitignore` files are considered;
- later patterns override earlier matching patterns within an applicable scope;
- directory-only patterns do not match regular files with the same name;
- a negation cannot re-include a descendant while its parent directory remains ignored;
- a nested ignore file can override a root rule when the parent directory is traversable;
- each `is_ignored()` call reads the current ignore files, so repeated checks observe policy
  changes in the same Python process; one `walk()` uses a single snapshot for a consistent
  traversal.

`initial_excludes` are caller-owned baseline exclusions. A matching baseline exclusion remains
ignored even if a repository `.gitignore` contains a later negation.

The portable library also reads the conventional global ignore file
(`$XDG_CONFIG_HOME/git/ignore`, or `~/.config/git/ignore`) and the discovered repository's
`info/exclude`. Repository `.gitignore` rules take precedence over these lower-priority sources.
When the supplied root is a subdirectory of a repository, applicable ancestor `.gitignore` files
are included. Git configuration overrides, conditional includes, and index state are not read.
Consequently, global and checkout-local exclusions can affect discovery and durability checks;
results do not guarantee that a file is absent from a clean checkout.

The mdrepo adapters preserve `ignored=None` (all entries), `ignored=True` (ignored entries),
`ignored=False` (included entries), tuple batch results, and rejection of `follow_links=True`.
Unlike the library's default, mdrepo retains an empty `initial_excludes` baseline. Pass
`initial_excludes=(".git",)` to exclude Git metadata in the Python API; Markdown discovery already
excludes `.git/**` through its default mdrepo configuration.

Pattern interpretation comes from the library rather than pathspec. For example, a trailing
backslash is accepted during parsing rather than reported as malformed. Invalid character ranges
such as `[z-a]` still raise `GitIgnoreError`. Error details are supplied by the library.

## mdrepo policy integration

The same evaluator powers `MDR006`, which reports existing links to Git-ignored targets. It also
controls Markdown discovery when `respect-gitignore = true` (the default) and prevents ignored
documents from creating orphan-graph noise. Set that option to `false` only when ignored Markdown
must be inspected explicitly; durability checks still report links to ignored targets.

Markdown discovery uses `GitIgnoreWalker.walk()` for regular-file and symlink-safe traversal. The
engine's Git-ignore filtering is combined with mdrepo's separate ordered `include` and `exclude`
policies; those policies are not silently merged into `.gitignore`.

The focused regression suite is in `tests/src/test_gitignore.py` and runs as part of the normal
`python -m pytest` and `python -m mdrepo check .` validation flow.
