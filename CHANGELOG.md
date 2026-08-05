# Changelog

Release versions are derived from Git tags by `setuptools-scm`. Version `0.0.1` is the first
non-prerelease release; the entries below document it and its preceding alpha sequence.

## 0.0.1.post0

- Clarified provider-neutral CI and pre-commit integration guidance.
- Aligned released-version examples and documented configuration defaults.
- Added mechanical checks to keep documentation contracts consistent with the implementation.

## 0.0.1

- Published the first non-prerelease package after validating the `0.0.1` alpha series.
- Consolidated the Git-ignore policy, portable-link, exact-case, document-reachability, and
  governed-exception checks into the released `mdrepo` package.
- Added provider-neutral CI and pre-commit integration guidance.

## 0.0.1a3

- Completed the repository Git-ignore policy integration, including nested rules, negations,
  contents-only patterns, safe traversal, explanations, and durable-target checks.
- Made Git-ignored Markdown respect discovery and orphan analysis by default while retaining an
  explicit opt-out.
- Split the public Git-ignore submodule into `GitIgnorePolicy` and `GitIgnoreWalker` and kept the
  package root limited to version metadata.
- Clarified the Git-ignore specification boundary and the division of responsibility between
  `mdrepo`, rumdl, and site generators.
- Refined default exclusions, CI integration documentation, test organization, and release
  validation.

## 0.0.1a2

- Added Git-ignore-aware Markdown discovery and orphan-graph eligibility filtering.
- Added configuration for respecting Git-ignore policy during discovery.
- Added coverage for nested ignore files, negations, malformed patterns, and transient targets.

## 0.0.1a1

- Corrected release metadata to use SPDX-compatible MIT license configuration.
- Improved wheel and source-distribution validation for dynamic setuptools-scm versions.

## 0.0.1a0

- Published the initial alpha of the repository-aware Markdown policy checker.
- Established the `mdrepo` distribution, import package, command, and configuration namespace.
- Added portable-link, exact-case, document-reachability, and governed-exception checks.
