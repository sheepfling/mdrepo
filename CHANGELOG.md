# Changelog

## 0.2.1

- Added an explicit responsibility contract defining the boundary between rumdl, `mdrepo`, network
  checking, and documentation-site builds.
- Documented one authoritative owner for missing targets, fragments, path portability, document
  reachability, and exception governance.
- Documented the canonical local-cleanup and CI workflows with rumdl.
- Reframed `MDR004` as a disabled standalone fallback rather than a normal paired rule.
- Clarified the difference between MkDocs navigation membership (`MD074`) and generic Markdown graph
  reachability (`MDR101`).
- Documented independent configuration, suppression, diagnostics, and exit-status ownership.
- Added a feature-admission and capability-retirement rule so `mdrepo` stays narrow as primary tools
  evolve.
- Added a repository-local CI runner covering compilation, Ruff, formatting, coverage tests,
  isolated sdist/wheel builds, Pyright, rumdl, and the `mdrepo`
  self-check.
- Added cross-platform CI coverage for Windows and Ubuntu on Python 3.12, 3.13, and 3.14.
- Added strict Pyright checking, branch coverage reporting, `twine check` packaging validation,
  and pre-commit configuration and hook validation.
- Made the repository's default orphan policy part of CI self-checks.
- Added regression coverage for stale exception reporting, home-relative destinations, and the
  interconnected repository scenario.
- Made the marker-compatible Ruff formatting check read-only and kept the standard CI coverage
  report informational rather than coupling it to a hardcoded threshold.
- Added reusable pseudo-repository test fixtures and expanded scenario coverage across Markdown
  parsing, filesystem resolution, graph reachability, rule toggles, exception suppression, CLI
  output modes, and dry-run versus applied fixes.
- Removed Scope Markers integration so Ruff, tests, and repository checks operate directly on the
  source tree without generated marker comments.
- Added a filesystem input-safety invariant and regression coverage preventing recursive discovery
  from admitting FIFOs or other non-regular entries for later reads.
- Resolved PyCharm-reported API, typing, shadowing, and expression issues, and tightened direct
  Ruff lint and formatting validation.
- Moved release tag verification, distribution building, and twine validation into a tested Python
  helper; GitLab CI delegates to the repository runner, while the final PyPI upload remains manual.
- Made repository tooling importable as a `scripts` package, with CI and release operations exposed
  through `python -m scripts.ci` and `python -m scripts.release`.
- Removed hosted repository URL normalization and provider-specific `MDR006`; external GitHub,
  GitLab, Bitbucket, and other hosted URLs are outside `mdrepo`'s policy scope.

## 0.2.0

- Reset the project around repository-aware policy instead of general Markdown linting.
- Removed Pluggy, entry-point discovery, external command orchestration, rumdl adapters, and Lychee
  integration.
- Added exact-case path checks, same-repository mutable-link conversion, rooted document graphs,
  structured exception health, CRLF-preserving atomic fixes, and text/JSON/GitHub output.
- Made missing-target checking opt-in so rumdl can remain authoritative for ordinary Markdown lint.
