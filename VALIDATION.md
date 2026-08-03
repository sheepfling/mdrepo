# Validation record

Validated on 2026-08-03 with CPython 3.14.6 on Windows.

## Completed

- `python -m compileall -q src scripts tests`
- 94 pytest tests passing
- 89% branch-aware coverage reported during the validation run
- Pyright strict-mode check: zero errors and zero warnings
- Ruff lint check: clean
- Marker-free Ruff formatting compatibility check: clean
- Ruff lint and formatting checks run directly on the repository sources
- Provider-neutral release metadata, build, and twine validation tests: clean
- rumdl check: clean
- Pre-commit configuration and published hook manifest validation: clean
- Pre-commit hook execution against `README.md`: clean
- Project self-check with orphan analysis enabled: zero findings
- Wheel and source-distribution construction through `setuptools.build_meta` in a temporary output
  directory
- `twine check` validation for both built distributions
- Wheel metadata inspection: only `markdown-it-py`, `pathspec`, and Pydantic runtime dependencies
- CRLF-preserving safe-fix test
- Responsibility documentation linked into the repository graph and covered by the self-check
- Full-directory checks report unused structured exceptions while partial file checks remain scoped
- Repository URL ports are validated and included in same-repository identity matching
- Home-relative Markdown destinations are rejected as machine-local paths
- The formatter regression check is read-only and verifies marker-free temporary source copies
- Reusable pseudo-repository fixture coverage for path selection, parser spans, resolver edge cases,
  graph serialization, rule toggles, structured suppression, and safe-fix modes
- Complete local `python scripts/ci.py` pass using the development environment

## Not completed in this environment

- The full GitLab CI matrix has not been observed from this workspace: the hosted Linux runners
  still need to execute the Python 3.12, 3.13, and 3.14 jobs.
- A real TestPyPI or PyPI publication has not been attempted. `scripts/release.py build` validates
  the distributions, while the final `twine upload` remains an intentional manual step.
