# Agent guidance

When asked to help adopt `rumdl` and `mdrepo` in another repository:

- Read [the adoption guide](docs/adopting.md) and [the CI integration guide](docs/ci-integration.md).
- Inspect the target repository's Markdown scope, existing tool configuration, dependencies, and CI
  before proposing edits. Preserve existing settings and CI structure.
- Use `mdrepo init` only when no mdrepo configuration exists. It creates a sidecar and refuses to
  overwrite discovered configuration. Ask the user to review its scope and choose real graph roots.
- When rumdl is installed, leave ordinary missing-file and heading-fragment checks to rumdl; enable
  mdrepo missing-target checks only for standalone use or an explicit policy decision.
- Keep both CI checks separate and run them after formatting, tests, and generated-file steps.
- Validate with the target repository's selected Python and installed tool versions. Report the
  exact commands and results, and distinguish local validation from hosted CI results.
